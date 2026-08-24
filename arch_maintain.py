#!/usr/bin/env python3
"""
Arch Linux Maintenance Script
Automates common system maintenance tasks
"""

import argparse
import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


class Colors:
    """ANSI color codes for terminal output.

    Call Colors.disable() to blank every code (e.g. when output is not a TTY
    or NO_COLOR is set) so escape sequences don't pollute logs.
    """
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    END = '\033[0m'

    @classmethod
    def disable(cls):
        cls.BLUE = cls.GREEN = cls.YELLOW = cls.RED = cls.BOLD = cls.END = ''


class ArchMaintenance:
    DEFAULT_LOG_FILE = Path.home() / '.local' / 'share' / 'arch-maintenance.log'

    def __init__(self, keep=3, noconfirm=False, dry_run=False,
                 skip_system=False, skip_aur=False, skip_cache=False,
                 skip_orphans=False, log_file=None):
        self.keep = keep
        self.noconfirm = noconfirm
        self.dry_run = dry_run
        self.skip_system = skip_system
        self.skip_aur = skip_aur
        self.skip_cache = skip_cache
        self.skip_orphans = skip_orphans

        self.log_file = Path(log_file) if log_file else self.DEFAULT_LOG_FILE
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.tasks_completed = []
        self.tasks_failed = []
        self.tasks_skipped = []

        # Name the logger per log file so distinct paths (e.g. in tests) get
        # isolated handlers rather than reusing the first one created.
        self.logger = logging.getLogger(f'arch-maintenance:{self.log_file}')
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = logging.FileHandler(self.log_file)
            handler.setFormatter(logging.Formatter(
                '[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
            self.logger.addHandler(handler)

    def log(self, message):
        """Log message to file with timestamp"""
        self.logger.info(message)

    def print_header(self, text):
        """Print a formatted header"""
        print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}\n")

    def print_success(self, text):
        """Print success message"""
        print(f"{Colors.GREEN}✓ {text}{Colors.END}")

    def print_error(self, text):
        """Print error message"""
        print(f"{Colors.RED}✗ {text}{Colors.END}")

    def print_info(self, text):
        """Print info message"""
        print(f"{Colors.YELLOW}→ {text}{Colors.END}")

    def maybe_noconfirm(self, cmd):
        """Append --noconfirm to a command when running non-interactively"""
        return cmd + ['--noconfirm'] if self.noconfirm else cmd

    def run_command(self, cmd, task_name):
        """Run a command and record the outcome. Returns True on success."""
        self.log(f"Running: {' '.join(cmd)}")

        if self.dry_run:
            self.print_info(f"[dry-run] {' '.join(cmd)}")
            self.tasks_completed.append(f"{task_name} (dry-run)")
            return True

        try:
            result = subprocess.run(cmd, text=True)
        except FileNotFoundError:
            self.tasks_failed.append(task_name)
            self.log(f"Command not found: {cmd[0]}")
            self.print_error(f"Command not found: {cmd[0]}")
            return False

        if result.returncode == 0:
            self.tasks_completed.append(task_name)
            self.log(f"Success: {task_name}")
            return True

        self.tasks_failed.append(task_name)
        self.log(f"Failed: {task_name} (exit code: {result.returncode})")
        self.print_error(f"Failed: {task_name} (exit code: {result.returncode})")
        return False

    def check_aur_helper(self):
        """Return the first available AUR helper, or None"""
        for helper in ['yay', 'paru']:
            if shutil.which(helper):
                return helper
        return None

    def update_system(self):
        """Update packages.

        An AUR helper (yay/paru) already performs a full system upgrade of the
        official repositories, so when one is present we run it alone rather
        than upgrading the official packages twice.
        """
        aur_helper = None if self.skip_aur else self.check_aur_helper()

        if aur_helper:
            self.print_header("Updating System + AUR Packages")
            self.print_info(f"Using AUR helper: {aur_helper}")
            return self.run_command(
                self.maybe_noconfirm([aur_helper, '-Syu']),
                "System + AUR update")

        self.print_header("Updating System Packages")
        if not self.skip_aur:
            self.print_info("No AUR helper found (yay or paru); "
                            "updating official packages only")
        self.print_info("Running: sudo pacman -Syu")
        return self.run_command(
            self.maybe_noconfirm(['sudo', 'pacman', '-Syu']),
            "System update")

    def clean_cache(self):
        """Clean package cache"""
        self.print_header("Cleaning Package Cache")

        if shutil.which('paccache'):
            self.print_info(f"Keeping {self.keep} most recent package versions")
            return self.run_command(
                ['sudo', 'paccache', '-r', f'-k{self.keep}'], "Cache cleaning")

        self.print_info("paccache not found, using pacman -Sc")
        return self.run_command(
            self.maybe_noconfirm(['sudo', 'pacman', '-Sc']), "Cache cleaning")

    def remove_orphans(self):
        """Remove orphaned packages.

        Removing orphans can orphan their now-unneeded dependencies in turn, so
        we repeat until no orphans remain (or a pass fails).
        """
        self.print_header("Removing Orphaned Packages")

        total_removed = 0
        while True:
            result = subprocess.run(
                ['pacman', '-Qtdq'], capture_output=True, text=True)

            if result.returncode != 0 or not result.stdout.strip():
                if total_removed == 0:
                    self.print_info("No orphaned packages found")
                else:
                    self.print_success(f"Removed {total_removed} orphaned package(s)")
                self.tasks_completed.append("Remove orphans")
                return True

            orphans = result.stdout.strip().split('\n')
            self.print_info(f"Found {len(orphans)} orphaned package(s)")

            if not self.run_command(
                    self.maybe_noconfirm(['sudo', 'pacman', '-Rns'] + orphans),
                    "Remove orphans"):
                return False
            total_removed += len(orphans)

            # In dry-run mode nothing is actually removed; avoid an infinite loop.
            if self.dry_run:
                return True

    def print_summary(self):
        """Print summary of completed tasks"""
        self.print_header("Maintenance Summary")

        if self.tasks_completed:
            print(f"{Colors.GREEN}{Colors.BOLD}Completed Tasks:{Colors.END}")
            for task in self.tasks_completed:
                print(f"  {Colors.GREEN}✓{Colors.END} {task}")

        if self.tasks_skipped:
            print(f"\n{Colors.YELLOW}{Colors.BOLD}Skipped Tasks:{Colors.END}")
            for task in self.tasks_skipped:
                print(f"  {Colors.YELLOW}−{Colors.END} {task}")

        if self.tasks_failed:
            print(f"\n{Colors.RED}{Colors.BOLD}Failed Tasks:{Colors.END}")
            for task in self.tasks_failed:
                print(f"  {Colors.RED}✗{Colors.END} {task}")

        print(f"\n{Colors.BOLD}Log file:{Colors.END} {self.log_file}")

    def prime_sudo(self):
        """Prime the sudo timestamp so the run doesn't stall waiting for a
        password prompt buried under pacman output. Skipped in dry-run."""
        if self.dry_run:
            return True
        self.print_info("Requesting sudo privileges...")
        try:
            return subprocess.run(['sudo', '-v']).returncode == 0
        except FileNotFoundError:
            self.print_error("sudo not found")
            return False

    def run(self):
        """Run all maintenance tasks"""
        start_time = datetime.now()
        self.log("=" * 60)
        self.log("Starting Arch Linux maintenance")

        print(f"{Colors.BOLD}{Colors.BLUE}")
        print("╔══════════════════════════════════════════════════════╗")
        print("║            Arch Linux Maintenance Script             ║")
        print("╚══════════════════════════════════════════════════════╝")
        print(Colors.END)

        if self.dry_run:
            self.print_info("Dry-run mode: no changes will be made")

        if not self.prime_sudo():
            self.print_error("Could not obtain sudo privileges; aborting")
            self.log("Aborted: failed to obtain sudo privileges")
            sys.exit(1)

        tasks = [
            (self.skip_system, "System update", self.update_system),
            (self.skip_cache, "Cache cleaning", self.clean_cache),
            (self.skip_orphans, "Remove orphans", self.remove_orphans),
        ]
        for skip, name, func in tasks:
            if skip:
                self.print_info(f"Skipping: {name}")
                self.tasks_skipped.append(name)
                self.log(f"Skipped: {name}")
                continue
            func()

        self.print_summary()

        duration = (datetime.now() - start_time).total_seconds()
        self.log(f"Maintenance completed in {duration:.0f} seconds")
        print(f"\n{Colors.BOLD}Time taken:{Colors.END} {duration:.0f} seconds")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Automate common Arch Linux maintenance tasks.")
    parser.add_argument(
        '-k', '--keep', type=int, default=3, metavar='N',
        help="Number of recent package versions to keep when cleaning cache "
             "(default: 3)")
    parser.add_argument(
        '-y', '--noconfirm', action='store_true',
        help="Pass --noconfirm to pacman/AUR helper (for unattended runs)")
    parser.add_argument(
        '-n', '--dry-run', action='store_true',
        help="Show what would be done without making any changes")
    parser.add_argument(
        '--no-color', action='store_true',
        help="Disable colored output")
    parser.add_argument('--skip-system', action='store_true',
                        help="Skip the system/AUR package update")
    parser.add_argument('--skip-aur', action='store_true',
                        help="Skip AUR updates (update official packages only)")
    parser.add_argument('--skip-cache', action='store_true',
                        help="Skip package cache cleaning")
    parser.add_argument('--skip-orphans', action='store_true',
                        help="Skip orphaned package removal")
    return parser.parse_args(argv)


def main():
    """Main entry point"""
    args = parse_args()

    # Disable color for non-interactive output (logs, pipes) or on request.
    if args.no_color or os.environ.get('NO_COLOR') or not sys.stdout.isatty():
        Colors.disable()

    # Check if running with appropriate privileges
    if os.geteuid() == 0:
        print(f"{Colors.RED}Warning: Don't run this script as root!{Colors.END}")
        print("The script will use sudo when needed.")
        sys.exit(1)

    try:
        maintenance = ArchMaintenance(
            keep=args.keep,
            noconfirm=args.noconfirm,
            dry_run=args.dry_run,
            skip_system=args.skip_system,
            skip_aur=args.skip_aur,
            skip_cache=args.skip_cache,
            skip_orphans=args.skip_orphans,
        )
        maintenance.run()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Interrupted by user{Colors.END}")
        sys.exit(130)
    except Exception as e:
        print(f"\n{Colors.RED}Unexpected error: {e}{Colors.END}")
        sys.exit(1)


if __name__ == "__main__":
    main()

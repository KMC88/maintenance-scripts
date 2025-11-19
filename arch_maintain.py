#!/usr/bin/env python3
"""
Arch Linux Maintenance Script
Automates common system maintenance tasks
"""

import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path


class Colors:
    """ANSI color codes for terminal output"""
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    END = '\033[0m'


class ArchMaintenance:
    def __init__(self):
        self.log_file = Path.home() / '.local' / 'share' / 'arch-maintenance.log'
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.tasks_completed = []
        self.tasks_failed = []

    def log(self, message):
        """Log message to file with timestamp"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(self.log_file, 'a') as f:
            f.write(f"[{timestamp}] {message}\n")

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

    def run_command(self, cmd, task_name, check=True):
        """Run a command and handle errors"""
        self.log(f"Running: {' '.join(cmd)}")
        try:
            result = subprocess.run(
                cmd,
                check=check,
                text=True,
                capture_output=False
            )
            if result.returncode == 0:
                self.tasks_completed.append(task_name)
                self.log(f"Success: {task_name}")
                return True
            else:
                self.tasks_failed.append(task_name)
                self.log(f"Failed: {task_name} (exit code: {result.returncode})")
                return False
        except subprocess.CalledProcessError as e:
            self.tasks_failed.append(task_name)
            self.log(f"Error: {task_name} - {str(e)}")
            self.print_error(f"Failed: {task_name}")
            return False
        except FileNotFoundError:
            self.tasks_failed.append(task_name)
            self.log(f"Command not found: {cmd[0]}")
            self.print_error(f"Command not found: {cmd[0]}")
            return False

    def check_aur_helper(self):
        """Check which AUR helper is available"""
        for helper in ['yay', 'paru']:
            if subprocess.run(['which', helper], capture_output=True).returncode == 0:
                return helper
        return None

    def update_system(self):
        """Update official packages with pacman"""
        self.print_header("Updating System Packages")
        self.print_info("Running: sudo pacman -Syu")
        return self.run_command(['sudo', 'pacman', '-Syu'], "System update")

    def update_aur(self):
        """Update AUR packages"""
        self.print_header("Updating AUR Packages")
        aur_helper = self.check_aur_helper()

        if not aur_helper:
            self.print_error("No AUR helper found (yay or paru)")
            self.tasks_failed.append("AUR update")
            return False

        self.print_info(f"Using AUR helper: {aur_helper}")
        return self.run_command([aur_helper, '-Syu', '--noconfirm'], "AUR update")

    def clean_cache(self):
        """Clean package cache"""
        self.print_header("Cleaning Package Cache")

        # Check if paccache is available
        if subprocess.run(['which', 'paccache'], capture_output=True).returncode != 0:
            self.print_info("paccache not found, using pacman -Sc")
            return self.run_command(['sudo', 'pacman', '-Sc', '--noconfirm'], "Cache cleaning")

        self.print_info("Keeping 3 most recent package versions")
        return self.run_command(['sudo', 'paccache', '-r'], "Cache cleaning")

    def remove_orphans(self):
        """Remove orphaned packages"""
        self.print_header("Removing Orphaned Packages")

        # First, check if there are any orphans
        result = subprocess.run(
            ['pacman', '-Qtdq'],
            capture_output=True,
            text=True
        )

        if result.returncode != 0 or not result.stdout.strip():
            self.print_info("No orphaned packages found")
            self.tasks_completed.append("Remove orphans")
            return True

        orphans = result.stdout.strip().split('\n')
        self.print_info(f"Found {len(orphans)} orphaned package(s)")

        return self.run_command(
            ['sudo', 'pacman', '-Rns', '--noconfirm'] + orphans,
            "Remove orphans"
        )

    def print_summary(self):
        """Print summary of completed tasks"""
        self.print_header("Maintenance Summary")

        if self.tasks_completed:
            print(f"{Colors.GREEN}{Colors.BOLD}Completed Tasks:{Colors.END}")
            for task in self.tasks_completed:
                print(f"  {Colors.GREEN}✓{Colors.END} {task}")

        if self.tasks_failed:
            print(f"\n{Colors.RED}{Colors.BOLD}Failed Tasks:{Colors.END}")
            for task in self.tasks_failed:
                print(f"  {Colors.RED}✗{Colors.END} {task}")

        print(f"\n{Colors.BOLD}Log file:{Colors.END} {self.log_file}")

    def run(self):
        """Run all maintenance tasks"""
        start_time = datetime.now()
        self.log("="*60)
        self.log("Starting Arch Linux maintenance")

        print(f"{Colors.BOLD}{Colors.BLUE}")
        print("╔════════════════════════════════════════════════════════╗")
        print("║         Arch Linux Maintenance Script                 ║")
        print("╚════════════════════════════════════════════════════════╝")
        print(Colors.END)

        # Run all tasks
        self.update_system()
        self.update_aur()
        self.clean_cache()
        self.remove_orphans()

        # Print summary
        self.print_summary()

        # Log completion time
        end_time = datetime.now()
        duration = (end_time - start_time).seconds
        self.log(f"Maintenance completed in {duration} seconds")
        print(f"\n{Colors.BOLD}Time taken:{Colors.END} {duration} seconds")


def main():
    """Main entry point"""
    # Check if running with appropriate privileges
    if os.geteuid() == 0:
        print(f"{Colors.RED}Warning: Don't run this script as root!{Colors.END}")
        print("The script will use sudo when needed.")
        sys.exit(1)

    try:
        maintenance = ArchMaintenance()
        maintenance.run()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Interrupted by user{Colors.END}")
        sys.exit(130)
    except Exception as e:
        print(f"\n{Colors.RED}Unexpected error: {e}{Colors.END}")
        sys.exit(1)


if __name__ == "__main__":
    main()

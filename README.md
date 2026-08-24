# Arch Linux Maintenance Script

[![Tests](https://github.com/KMC88/maintenance-scripts/actions/workflows/tests.yml/badge.svg)](https://github.com/KMC88/maintenance-scripts/actions/workflows/tests.yml)

Automated maintenance script for Arch Linux systems. Handles system updates, AUR updates, cache cleaning, and orphan removal.

## Features

- **System Updates**: Updates all packages. If an AUR helper (`yay`/`paru`) is
  present it performs the full system upgrade in one pass (official + AUR);
  otherwise it falls back to `pacman -Syu`.
- **Cache Cleaning**: Removes old package versions (keeps 3 most recent by
  default, configurable with `--keep`)
- **Orphan Removal**: Repeatedly finds and removes orphaned packages until none
  remain
- **Logging**: All operations logged to `~/.local/share/arch-maintenance.log`
- **Color Output**: Terminal output with status indicators, automatically
  disabled for non-interactive output (cron/systemd) or when `NO_COLOR` is set
- **Error Handling**: Graceful error handling with summary report
- **Configurable**: Command-line flags to skip tasks, run unattended, or preview
  changes with `--dry-run`

## Requirements

- Python 3.6+
- `sudo` privileges
- `pacman` (installed by default)
- `yay` or `paru` (for AUR updates)
- `paccache` (optional, from `pacman-contrib` package)

### Install Optional Dependencies

```bash
sudo pacman -S pacman-contrib    # For paccache
yay -S yay                        # AUR helper (if not installed)
```

## Installation

1. Clone or download the script:
```bash
cd ~/arch-maintenance
```

2. Make it executable (already done):
```bash
chmod +x arch_maintain.py
```

3. Optionally, create a symlink for easy access:
```bash
sudo ln -s ~/arch-maintenance/arch_maintain.py /usr/local/bin/arch-maintain
```

## Usage

### Basic Usage

```bash
./arch_maintain.py
```

Or if you created the symlink:
```bash
arch-maintain
```

### What It Does

The script will automatically:
1. Update all packages (official + AUR in one pass if yay/paru is installed)
2. Clean package cache (keeping the 3 most recent versions)
3. Remove orphaned packages (repeated until none remain)

### Options

```
-k, --keep N     Number of recent package versions to keep (default: 3)
-y, --noconfirm  Pass --noconfirm to pacman/AUR helper (unattended runs)
-n, --dry-run    Show what would be done without making any changes
--no-color       Disable colored output
--skip-system    Skip the system/AUR package update
--skip-aur       Skip AUR updates (update official packages only)
--skip-cache     Skip package cache cleaning
--skip-orphans   Skip orphaned package removal
```

Examples:
```bash
./arch_maintain.py --dry-run          # Preview actions, change nothing
./arch_maintain.py -y                 # Unattended (no confirmation prompts)
./arch_maintain.py --keep 5           # Keep 5 cached versions per package
./arch_maintain.py --skip-orphans     # Everything except orphan removal
```

### Example Output

```
╔══════════════════════════════════════════════════════╗
║            Arch Linux Maintenance Script             ║
╚══════════════════════════════════════════════════════╝

→ Requesting sudo privileges...

============================================================
Updating System + AUR Packages
============================================================

→ Using AUR helper: yay
[yay output...]
✓ System + AUR update

============================================================
Maintenance Summary
============================================================

Completed Tasks:
  ✓ System + AUR update
  ✓ Cache cleaning
  ✓ Remove orphans

Log file: /home/kmcerlean/.local/share/arch-maintenance.log
Time taken: 45 seconds
```

## Automation

### Run Daily with Systemd Timer

1. Create a systemd service:
```bash
sudo nano /etc/systemd/system/arch-maintenance.service
```

Add:
```ini
[Unit]
Description=Arch Linux Maintenance
After=network-online.target

[Service]
Type=oneshot
User=YOUR_USERNAME
ExecStart=/home/YOUR_USERNAME/arch-maintenance/arch_maintain.py --noconfirm
```

2. Create a timer:
```bash
sudo nano /etc/systemd/system/arch-maintenance.timer
```

Add:
```ini
[Unit]
Description=Run Arch maintenance daily

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
```

3. Enable and start:
```bash
sudo systemctl enable arch-maintenance.timer
sudo systemctl start arch-maintenance.timer
```

### Run with Cron

Add to crontab:
```bash
crontab -e
```

Add line (runs at 2 AM daily):
```
0 2 * * * /home/YOUR_USERNAME/arch-maintenance/arch_maintain.py --noconfirm
```

> **Note on unattended runs:** With no interactive terminal, `sudo` cannot
> prompt for a password. For cron/systemd runs to succeed you must grant
> passwordless sudo for the relevant commands, e.g. in `visudo`:
> ```
> YOUR_USERNAME ALL=(root) NOPASSWD: /usr/bin/pacman, /usr/bin/paccache
> ```
> Colored output is automatically disabled when not attached to a terminal, so
> logs stay clean.

## Logs

All operations are logged to:
```
~/.local/share/arch-maintenance.log
```

View recent logs:
```bash
tail -n 50 ~/.local/share/arch-maintenance.log
```

## Testing

The test suite uses only the standard library (`unittest`), so no extra
packages are needed. Every external command is mocked, so the tests never touch
`pacman`, `sudo`, or your real system:

```bash
python3 -m unittest -v
```

## Customization

Edit `arch_maintain.py` to customize:
- Which tasks to run
- Number of package versions to keep
- Log file location
- Add additional maintenance tasks

## Safety

- Script requires sudo password for privileged operations
- Refuses to run as root (for safety)
- All operations are logged
- Uses `--noconfirm` for automation (review code if concerned)

## Troubleshooting

**No AUR helper found:**
```bash
sudo pacman -S --needed base-devel git
git clone https://aur.archlinux.org/yay.git
cd yay
makepkg -si
```

**Permission denied:**
```bash
chmod +x arch_maintain.py
```

**paccache not found:**
```bash
sudo pacman -S pacman-contrib
```

## Contributing

Feel free to modify and extend this script for your needs!

## License

Licensed under the [MIT License](LICENSE) - feel free to use and modify as needed.

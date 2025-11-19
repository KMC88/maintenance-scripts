# Arch Linux Maintenance Script

Automated maintenance script for Arch Linux systems. Handles system updates, AUR updates, cache cleaning, and orphan removal.

## Features

- **System Updates**: Updates all official packages via `pacman -Syu`
- **AUR Updates**: Updates AUR packages using `yay` or `paru`
- **Cache Cleaning**: Removes old package versions (keeps 3 most recent)
- **Orphan Removal**: Finds and removes orphaned packages
- **Logging**: All operations logged to `~/.local/share/arch-maintenance.log`
- **Color Output**: Beautiful terminal output with status indicators
- **Error Handling**: Graceful error handling with summary report

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
1. Update all system packages
2. Update AUR packages (if yay/paru is installed)
3. Clean package cache (keeping 3 recent versions)
4. Remove orphaned packages

### Example Output

```
╔════════════════════════════════════════════════════════╗
║         Arch Linux Maintenance Script                 ║
╚════════════════════════════════════════════════════════╝

============================================================
Updating System Packages
============================================================

→ Running: sudo pacman -Syu
[pacman output...]
✓ System update

============================================================
Maintenance Summary
============================================================

Completed Tasks:
  ✓ System update
  ✓ AUR update
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
ExecStart=/home/YOUR_USERNAME/arch-maintenance/arch_maintain.py
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
0 2 * * * /home/YOUR_USERNAME/arch-maintenance/arch_maintain.py
```

## Logs

All operations are logged to:
```
~/.local/share/arch-maintenance.log
```

View recent logs:
```bash
tail -n 50 ~/.local/share/arch-maintenance.log
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

MIT License - Feel free to use and modify as needed.

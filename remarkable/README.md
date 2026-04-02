# reMarkable Metadata Backup

Fetch `.metadata`, `.content`, and `.pagedata` files from a reMarkable tablet over USB/SSH.

Two scripts are provided — use whichever matches the machine connected to the tablet:

| Script | Platform | Dependencies |
|--------|----------|-------------|
| `remarkable_metadata.py` | macOS / Linux | Python 3, `sshpass` (optional) |
| `remarkable_metadata.ps1` | Windows 10+ | None (OpenSSH + tar are built-in) |

## Setup

1. Connect the reMarkable tablet via USB
2. Find the SSH password on the tablet: **Settings > Help > Copyrights and licenses** (bottom of screen)
3. Copy `.env.example` to `.env` and add the password:
   ```
   REMARKABLE_PASSWORD=your_password_here
   ```
   Without a `.env` file the scripts still work — you'll just get one password prompt.

## Usage

**macOS / Linux:**
```bash
# Preview files on the tablet
python remarkable_metadata.py --dry-run

# Download metadata files
python remarkable_metadata.py

# Custom output directory
python remarkable_metadata.py -o ~/Desktop/rm_backup
```

**Windows (PowerShell):**
```powershell
# Preview files on the tablet
.\remarkable_metadata.ps1 -DryRun

# Download metadata files
.\remarkable_metadata.ps1

# Custom output directory
.\remarkable_metadata.ps1 -OutputDir "C:\Users\me\Desktop\rm_backup"
```

## Output

Files are saved to `./backup/` by default. The scripts download three file types per document:

| Extension | Contents |
|-----------|----------|
| `.metadata` | Document name, type, parent folder, timestamps, deleted status |
| `.content` | Page count, page UUIDs, file type, pen/tool settings |
| `.pagedata` | Background template per page (Blank, Lined, Grid, etc.) |

Each file is named by its UUID on the tablet (e.g., `a1b2c3d4-e5f6-7890-abcd-ef1234567890.metadata`).

After copying, a summary is printed showing each document's name and type.

## Password Automation

Without a `.env` file you get a single password prompt (the scripts use one SSH+tar session for the entire transfer).

For fully automated runs, create a `.env` file and:

- **macOS:** install `sshpass` — `brew install hudochenkov/sshpass/sshpass`
- **Windows:** no extra install needed (uses `SSH_ASKPASS`)

## Notes

- The tablet's USB IP is `10.11.99.1` (override with `--host` / `-TabletHost`)
- SSH user is `root` (override with `--user` / `-User`)
- On reMarkable Paper Pro, SSH may need to be enabled via developer mode
- The `.env` file is gitignored to prevent committing the password

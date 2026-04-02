"""
Fetch metadata files from a reMarkable tablet over USB/SSH.

Copies .metadata, .content, and .pagedata files for every document
on the device to a local directory, preserving the UUID filenames.

Reads REMARKABLE_PASSWORD from a .env file (if present) to avoid
password prompts. Requires `sshpass` for automated auth:
    brew install hudochenkov/sshpass/sshpass
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REMARKABLE_HOST = "10.11.99.1"
REMARKABLE_USER = "root"
REMARKABLE_DOCS_PATH = "/home/root/.local/share/remarkable/xochitl"

LOCAL_OUTPUT_DIR = Path(__file__).parent / "backup"

METADATA_EXTENSIONS = [".metadata", ".content", ".pagedata"]


def load_env(env_path: Path) -> None:
    """Load key=value pairs from a .env file into os.environ."""
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def get_password() -> str | None:
    """Return the reMarkable password from env, or None."""
    return os.environ.get("REMARKABLE_PASSWORD") or None


def ssh_base_cmd(user: str, host: str, password: str | None) -> list[str]:
    """Build the base ssh command, with sshpass if a password is available."""
    if password:
        return ["sshpass", "-p", password, "ssh", "-o", "StrictHostKeyChecking=no", f"{user}@{host}"]
    return ["ssh", f"{user}@{host}"]


def run_ssh(user: str, host: str, password: str | None, remote_cmd: str, **kwargs) -> subprocess.CompletedProcess:
    """Run a command on the reMarkable via SSH."""
    cmd = ssh_base_cmd(user, host, password) + [remote_cmd]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30, **kwargs)


def list_metadata_files(user: str, host: str, password: str | None) -> list[str]:
    """List all metadata-related files on the device."""
    extensions_find = " -o ".join(
        f'-name "*.{ext.lstrip(".")}"' for ext in METADATA_EXTENSIONS
    )
    cmd = f"find {REMARKABLE_DOCS_PATH} -maxdepth 1 \\( {extensions_find} \\) -type f"

    result = run_ssh(user, host, password, cmd)
    if result.returncode != 0:
        print(f"Error listing files: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
    return files


def copy_files_tar(user: str, host: str, password: str | None, output_dir: Path) -> None:
    """Copy all metadata files in a single SSH session using tar."""
    output_dir.mkdir(parents=True, exist_ok=True)

    globs = " ".join(f"*.{ext.lstrip('.')}" for ext in METADATA_EXTENSIONS)
    remote_cmd = f"cd {REMARKABLE_DOCS_PATH} && tar cf - {globs} 2>/dev/null"

    ssh_cmd = ssh_base_cmd(user, host, password) + [remote_cmd]

    print("  Streaming files via tar...")
    result = subprocess.run(
        ssh_cmd,
        capture_output=True,
        timeout=120,
    )
    if result.returncode not in (0, 1):
        # tar returns 1 if some files changed during read, which is ok
        print(f"  Warning: ssh/tar returned exit code {result.returncode}", file=sys.stderr)

    # Extract tar from stdout
    tar_extract = subprocess.run(
        ["tar", "xf", "-", "-C", str(output_dir)],
        input=result.stdout,
        capture_output=True,
        timeout=30,
    )
    if tar_extract.returncode != 0:
        print(f"  Warning: tar extract error: {tar_extract.stderr.decode()}", file=sys.stderr)


def summarise(output_dir: Path) -> None:
    """Print a summary of what was downloaded."""
    metadata_files = sorted(output_dir.glob("*.metadata"))

    print(f"\n{'='*60}")
    print(f"Downloaded {len(metadata_files)} documents\n")

    for mf in metadata_files:
        try:
            data = json.loads(mf.read_text())
            name = data.get("visibleName", "(unknown)")
            doc_type = data.get("type", "")
            parent = data.get("parent", "")
            deleted = data.get("deleted", False)

            label = "FOLDER" if doc_type == "CollectionType" else "DOC"
            status = " [DELETED]" if deleted else ""
            location = f" (in: {parent[:8]}...)" if parent and parent != "trash" else ""
            if parent == "trash":
                location = " (in: trash)"

            print(f"  [{label}] {name}{status}{location}")
        except (json.JSONDecodeError, OSError):
            print(f"  [?] {mf.name} (could not parse)")

    print(f"\nFiles saved to: {output_dir}")


def main():
    parser = argparse.ArgumentParser(description="Backup reMarkable tablet metadata files.")
    parser.add_argument("--host", default=REMARKABLE_HOST, help=f"Tablet IP (default: {REMARKABLE_HOST})")
    parser.add_argument("--user", default=REMARKABLE_USER, help=f"SSH user (default: {REMARKABLE_USER})")
    parser.add_argument("-o", "--output", type=Path, default=LOCAL_OUTPUT_DIR, help="Local output directory")
    parser.add_argument("--dry-run", action="store_true", help="List files without copying")
    args = parser.parse_args()

    # Load .env from script directory
    load_env(Path(__file__).parent / ".env")
    password = get_password()

    if password:
        print("Using password from .env file")
    else:
        print("No .env password found — SSH will prompt for password")

    print(f"Connecting to {args.user}@{args.host}...")
    print(f"Scanning {REMARKABLE_DOCS_PATH} for metadata files...\n")

    remote_files = list_metadata_files(args.user, args.host, password)

    by_ext: dict[str, list[str]] = {}
    for f in remote_files:
        ext = Path(f).suffix
        by_ext.setdefault(ext, []).append(f)

    for ext in METADATA_EXTENSIONS:
        count = len(by_ext.get(ext, []))
        print(f"  Found {count} {ext} files")

    print(f"\n  Total: {len(remote_files)} files")

    if args.dry_run:
        print("\nFiles that would be copied:")
        for f in remote_files:
            print(f"  {Path(f).name}")
        print("\nDry run — no files copied.")
        return

    print(f"\nCopying to {args.output}...")
    copy_files_tar(args.user, args.host, password, args.output)

    summarise(args.output)


if __name__ == "__main__":
    main()

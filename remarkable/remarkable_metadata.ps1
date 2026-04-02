<#
.SYNOPSIS
    Fetch metadata files from a reMarkable tablet over USB/SSH.
.DESCRIPTION
    Copies .metadata, .content, and .pagedata files for every document
    on the device to a local directory, preserving the UUID filenames.
    No Python required — runs on any Windows 10+ machine with OpenSSH.

    Reads REMARKABLE_PASSWORD from a .env file (if present) to avoid
    password prompts. Uses scp with wildcard patterns for transfer.
.PARAMETER TabletIP
    Tablet IP address (default: 10.11.99.1 for USB connection)
.PARAMETER SshUser
    SSH username (default: root)
.PARAMETER OutputDir
    Local directory for downloaded files (default: .\backup)
.PARAMETER DryRun
    List files without copying
.EXAMPLE
    .\remarkable_metadata.ps1
    .\remarkable_metadata.ps1 -DryRun
    .\remarkable_metadata.ps1 -OutputDir "C:\Users\me\Desktop\rm_backup"
#>

param(
    [string]$TabletIP = "10.11.99.1",
    [string]$SshUser = "root",
    [string]$OutputDir = (Join-Path $PSScriptRoot "backup"),
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$RemoteDocsPath = "/home/root/.local/share/remarkable/xochitl"
$Extensions = @(".metadata", ".content", ".pagedata")
$SshTarget = "${SshUser}@${TabletIP}"

# --- Load .env file ---
$envFile = Join-Path $PSScriptRoot ".env"
$Password = $null

if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $key, $value = $line -split "=", 2
            if ($key.Trim() -eq "REMARKABLE_PASSWORD" -and $value.Trim()) {
                $Password = $value.Trim()
            }
        }
    }
}

# --- Setup SSH_ASKPASS if password is available ---
if ($Password) {
    Write-Host "Using password from .env file"
    $askPassScript = Join-Path $env:TEMP "rm_askpass.bat"
    Set-Content -Path $askPassScript -Value "@echo $Password"
    $env:SSH_ASKPASS = $askPassScript
    $env:SSH_ASKPASS_REQUIRE = "force"
    $env:DISPLAY = "none"
} else {
    Write-Host "No .env password found - SSH will prompt for password"
}

# --- Check that ssh is available ---
if (-not (Get-Command "ssh" -ErrorAction SilentlyContinue)) {
    Write-Error "ssh not found. Ensure OpenSSH is installed (Settings > Apps > Optional Features > OpenSSH Client)."
    exit 1
}

$SshBase = @("ssh", "-o", "StrictHostKeyChecking=no", $SshTarget)

# --- List metadata files on the device ---
Write-Host "Connecting to $SshTarget..."
Write-Host "Scanning $RemoteDocsPath for metadata files...`n"

$findParts = ($Extensions | ForEach-Object { "-name `"*$_`"" }) -join " -o "
$findCmd = "find $RemoteDocsPath -maxdepth 1 \( $findParts \) -type f"

$sshArgs = $SshBase + @($findCmd)
$sshStdout = $null
$sshStderr = $null
$sshStdout = & $sshArgs[0] $sshArgs[1..($sshArgs.Count-1)] 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Error "SSH failed (exit code $LASTEXITCODE)"
    exit 1
}

$remoteFiles = ($sshStdout -split "`n") | Where-Object { $_.Trim() -ne "" }

if ($remoteFiles.Count -eq 0) {
    Write-Host "No metadata files found on the device."
    exit 0
}

# --- Count by extension ---
foreach ($ext in $Extensions) {
    $count = ($remoteFiles | Where-Object { $_ -like "*$ext" }).Count
    Write-Host "  Found $count $ext files"
}
Write-Host "`n  Total: $($remoteFiles.Count) files"

# --- Dry run exit ---
if ($DryRun) {
    Write-Host "`nFiles that would be copied:"
    foreach ($f in $remoteFiles) {
        Write-Host "  $(Split-Path $f -Leaf)"
    }
    Write-Host "`nDry run - no files copied."
    exit 0
}

# --- Copy files via scp (one call per extension) ---
if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}

Write-Host "`nCopying to $OutputDir..."

foreach ($ext in $Extensions) {
    $remotePath = "${SshTarget}:${RemoteDocsPath}/*${ext}"
    Write-Host "  Copying *$ext files..."
    & scp -o StrictHostKeyChecking=no $remotePath "$OutputDir\" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "scp returned exit code $LASTEXITCODE for *$ext"
    }
}

# Clean up askpass script if created
if ($Password) {
    Remove-Item (Join-Path $env:TEMP "rm_askpass.bat") -ErrorAction SilentlyContinue
}

# --- Summary ---
$metadataFiles = Get-ChildItem -Path $OutputDir -Filter "*.metadata" | Sort-Object Name

Write-Host "`n$('=' * 60)"
Write-Host "Downloaded $($metadataFiles.Count) documents`n"

foreach ($mf in $metadataFiles) {
    try {
        $data = Get-Content $mf.FullName -Raw | ConvertFrom-Json
        $name = if ($data.visibleName) { $data.visibleName } else { "(unknown)" }
        $label = if ($data.type -eq "CollectionType") { "FOLDER" } else { "DOC" }
        $status = if ($data.deleted) { " [DELETED]" } else { "" }
        $location = ""
        if ($data.parent -eq "trash") {
            $location = " (in: trash)"
        } elseif ($data.parent) {
            $location = " (in: $($data.parent.Substring(0, [Math]::Min(8, $data.parent.Length)))...)"
        }
        Write-Host "  [$label] ${name}${status}${location}"
    } catch {
        Write-Host "  [?] $($mf.Name) (could not parse)"
    }
}

Write-Host "`nFiles saved to: $OutputDir"

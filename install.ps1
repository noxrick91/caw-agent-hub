# caw-agent Windows installer.
#   irm https://agent.noxcaw.com/install.ps1 | iex
# Env: CAW_TAG  CAW_GITHUB  PREFIX  BIN_DIR
$ErrorActionPreference = "Stop"

$Repo = if ($env:CAW_GITHUB) { $env:CAW_GITHUB } else { "noxrick91/caw-agent-hub" }
$Prefix = if ($env:PREFIX) { $env:PREFIX } else { Join-Path $env:USERPROFILE ".caw-agent" }
$BinDir = if ($env:BIN_DIR) { $env:BIN_DIR } else { Join-Path $Prefix "bin" }
$Tag = if ($env:CAW_TAG) { $env:CAW_TAG } else { "latest" }
if ($Tag -eq "now") { $Tag = "latest" }
if ($Tag -match '^[0-9]') { $Tag = "v$Tag" }

$Arch = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture
if ($Arch -ne "X64") {
    throw "unsupported Windows architecture $Arch (need x64)"
}

$Asset = "caw-agent-x86_64-pc-windows-msvc.exe"
$Dest = Join-Path $BinDir "caw-agent.exe"
if ($Tag -eq "latest") {
    $Base = "https://github.com/$Repo/releases/latest/download"
} else {
    $Base = "https://github.com/$Repo/releases/download/$Tag"
}

Write-Host ""
Write-Host "caw-agent installer"
Write-Host "  $Asset -> $Dest"

if ((Test-Path $Dest) -and $Tag -eq "latest") {
    Write-Host "Existing install found — running caw-agent upgrade now"
    & $Dest upgrade now
    exit $LASTEXITCODE
}

New-Item -ItemType Directory -Force -Path $BinDir | Out-Null

function Get-RemoteFile([string]$Url, [string]$OutFile) {
    try {
        Invoke-WebRequest -UseBasicParsing -Uri $Url -OutFile $OutFile
    } catch {
        $code = $_.Exception.Response.StatusCode.value__
        if ($code -eq 404) {
            throw "not found: $Url`n  no public Release yet — https://github.com/$Repo/releases"
        }
        if ($code -eq 403 -or $code -eq 429) {
            throw "GitHub HTTP $code. Set GH_TOKEN or CAW_GITHUB_TOKEN and retry."
        }
        throw
    }
}

$Tmp = Join-Path $env:TEMP ("caw-agent-install-" + [guid]::NewGuid())
New-Item -ItemType Directory -Force -Path $Tmp | Out-Null
try {
    $Sums = Join-Path $Tmp "SHA256SUMS"
    $Bin = Join-Path $Tmp $Asset
    Get-RemoteFile "$Base/SHA256SUMS" $Sums
    Get-RemoteFile "$Base/$Asset" $Bin
    $Expect = (Get-Content $Sums | Where-Object { $_ -match [regex]::Escape($Asset) } | Select-Object -First 1) `
        -split '\s+' | Select-Object -First 1
    if (-not $Expect) { throw "SHA256SUMS has no entry for $Asset" }
    $Got = (Get-FileHash -Algorithm SHA256 -Path $Bin).Hash.ToLowerInvariant()
    if ($Got -ne $Expect.ToLowerInvariant()) {
        throw "SHA256 mismatch: got $Got expected $Expect"
    }
    if (Test-Path $Dest) { Copy-Item $Dest "$Dest.bak" -Force -ErrorAction SilentlyContinue }
    Copy-Item $Bin $Dest -Force
} finally {
    Remove-Item $Tmp -Recurse -Force -ErrorAction SilentlyContinue
}

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (-not $userPath) { $userPath = "" }
$onPath = $userPath -split ';' | Where-Object { $_ -and ($_ -ieq $BinDir) }
if (-not $onPath) {
    [Environment]::SetEnvironmentVariable("Path", "$BinDir;$userPath", "User")
    $env:Path = "$BinDir;$env:Path"
    Write-Host "Added to user PATH: $BinDir"
}

$Ver = ""
try { $Ver = (& $Dest --version 2>$null) } catch { }
Write-Host "Installation complete."
if ($Ver) { Write-Host "  version  $Ver" }
Write-Host "  binary   $Dest"
Write-Host "  sha256   $Got"
Write-Host ""
Write-Host "  caw-agent --help"
Write-Host "  caw-agent upgrade --check"
Write-Host ""

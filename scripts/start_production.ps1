<#
.SYNOPSIS
    LAXMAN-AUTONOMOUS MASTER SYSTEM: Production Launcher for Windows PowerShell
.DESCRIPTION
    Performs preflight runtime checks (Python, Node, Chrome, FFmpeg), verifies port availability,
    launches the FastAPI backend and frontend UI, and monitors health.
#>

[CmdletBinding()]
param(
    [string]$HostAddress = "127.0.0.1",
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " LAXMAN-AUTONOMOUS MASTER SYSTEM: Production Launch" -ForegroundColor Cyan
Write-Host " Repository Root: $ProjectRoot" -ForegroundColor Gray
Write-Host "=================================================================" -ForegroundColor Cyan

# 1. Preflight: Python Runtime
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    Write-Host "[ERROR] Python virtual environment not found at: $PythonExe" -ForegroundColor Red
    Write-Host "        Create it with: python -m venv .venv" -ForegroundColor Yellow
    Write-Host "        Then install:   .venv\Scripts\pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}
$PyVer = & $PythonExe --version 2>&1
Write-Host "[OK] Python Runtime: $PyVer ($PythonExe)" -ForegroundColor Green

# 2. Preflight: Node & npm
try {
    $NodeVer = (node -v).Trim()
    $NpmVer = (npm -v).Trim()
    Write-Host "[OK] Node.js Runtime: $NodeVer | npm: $NpmVer" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Node.js or npm is not available on PATH." -ForegroundColor Red
    Write-Host "        Node.js v20+ is required for Remotion and frontend UI." -ForegroundColor Yellow
    exit 1
}

# 3. Preflight: FFmpeg & ffprobe
$FfmpegPath = (Get-Command "ffmpeg" -ErrorAction SilentlyContinue)?.Source
$FfprobePath = (Get-Command "ffprobe" -ErrorAction SilentlyContinue)?.Source
if ($FfmpegPath -and $FfprobePath) {
    Write-Host "[OK] FFmpeg: $FfmpegPath" -ForegroundColor Green
    Write-Host "[OK] ffprobe: $FfprobePath" -ForegroundColor Green
} else {
    Write-Host "[WARN] FFmpeg or ffprobe missing from PATH. Media probing and video encoding may be limited." -ForegroundColor Yellow
}

# 4. Preflight: Google Chrome / Headless Browser
$BrowserScript = "from UI.backend import orchestrator; b, s = orchestrator.find_browser_executable(); print(f'{b} ({s})')"
$BrowserInfo = & $PythonExe -c $BrowserScript 2>&1
if ($BrowserInfo -match "None") {
    Write-Host "[WARN] No host Chrome executable detected. Remotion rendering will require PUPPETEER_EXECUTABLE_PATH." -ForegroundColor Yellow
} else {
    Write-Host "[OK] Browser Executable: $BrowserInfo" -ForegroundColor Green
}

# 5. Check Port Availability
$BackendInUse = (Get-NetTCPConnection -LocalPort $BackendPort -State Listen -ErrorAction SilentlyContinue)
$FrontendInUse = (Get-NetTCPConnection -LocalPort $FrontendPort -State Listen -ErrorAction SilentlyContinue)

if ($BackendInUse) {
    Write-Host "[INFO] Port $BackendPort is already active. Assuming backend is running." -ForegroundColor Yellow
} else {
    Write-Host "[START] Launching Backend API on $HostAddress:$BackendPort ..." -ForegroundColor Cyan
    $BackendJob = Start-Process -FilePath $PythonExe `
        -ArgumentList "-m uvicorn UI.backend.main:app --host $HostAddress --port $BackendPort" `
        -WorkingDirectory $ProjectRoot `
        -PassThru
}

if ($FrontendInUse) {
    Write-Host "[INFO] Port $FrontendPort is already active. Assuming UI is running." -ForegroundColor Yellow
} else {
    Write-Host "[START] Launching Frontend UI on port $FrontendPort ..." -ForegroundColor Cyan
    $FrontendDir = Join-Path $ProjectRoot "UI\frontend"
    $FrontendJob = Start-Process -FilePath "npm.cmd" `
        -ArgumentList "run dev" `
        -WorkingDirectory $FrontendDir `
        -PassThru
}

# 6. Wait for Backend Health
Write-Host "Waiting for Backend health check at http://${HostAddress}:${BackendPort}/health ..." -NoNewline
$MaxWaitSec = 30
$Healthy = $false
for ($i = 0; $i -lt $MaxWaitSec; $i++) {
    try {
        $resp = Invoke-RestMethod -Uri "http://${HostAddress}:${BackendPort}/health" -TimeoutSec 2 -ErrorAction Stop
        if ($resp.ok -eq $true) {
            $Healthy = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 1
        Write-Host "." -NoNewline
    }
}
Write-Host ""

if ($Healthy) {
    Write-Host "[READY] Backend API healthy and operational!" -ForegroundColor Green
} else {
    Write-Host "[WARN] Backend health check timed out. Inspect backend process logs." -ForegroundColor Yellow
}

# 7. Open Browser
if (-not $NoBrowser) {
    $UiUrl = "http://localhost:$FrontendPort"
    Write-Host "[LAUNCH] Opening Web UI at $UiUrl ..." -ForegroundColor Cyan
    Start-Process $UiUrl
}

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " Application is running! Press Ctrl+C or close windows to stop." -ForegroundColor Green
Write-Host " Backend API: http://${HostAddress}:${BackendPort}" -ForegroundColor White
Write-Host " Frontend UI: http://localhost:${FrontendPort}" -ForegroundColor White
Write-Host "=================================================================" -ForegroundColor Cyan

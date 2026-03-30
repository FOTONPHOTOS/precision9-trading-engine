# Master Launch Script for the Arsenal Ecosystem

Write-Host "=================================================" -ForegroundColor Green
Write-Host "  🚀 Launching Precision9 Arsenal Ecosystem 🚀"
Write-Host "================================================="

# --- Configuration ---
$pythonPath = "G:\python files\precision9\myenv_fixed\Scripts\python.exe"
$baseDir = "G:\python files\precision9\Simulation Environment\Trendline_Detectory"

# --- Symbol to Trade ---
# You can change this to BNBUSDT, ETHUSDT, SOLUSDT, etc.
$symbol = "BNBUSDT"


# 1. Launch Helios Server
Write-Host "[1/3] Launching Helios Server..." -ForegroundColor Yellow
$heliosArgs = "-NoExit -Command `"cd '$baseDir'; & '$pythonPath' helios_server.py`""
Start-Process pwsh -ArgumentList $heliosArgs

# Wait for server to initialize
Start-Sleep -Seconds 8

# 2. Launch Aegis Risk Manager
Write-Host "[2/3] Launching Aegis Risk Manager..." -ForegroundColor Yellow
$aegisDir = Join-Path $baseDir "eyes_of_horus"
$aegisArgs = "-NoExit -Command `"cd '$aegisDir'; & '$pythonPath' main.py`""
Start-Process pwsh -ArgumentList $aegisArgs

# Wait for server to initialize
Start-Sleep -Seconds 5

# 3. Launch the Main Arsenal Bot
Write-Host "[3/3] Launching Arsenal Bot for $symbol..." -ForegroundColor Cyan
$arsenalArgs = "-NoExit -Command `"cd '$baseDir'; & '$pythonPath' live_arsenal_horus_integrated.py --fast --symbol $symbol`""
Start-Process pwsh -ArgumentList $arsenalArgs

Write-Host "
✅ All systems launched in new windows." -ForegroundColor Green
Write-Host "Please monitor the individual windows for logs."

# launch_all_bots.ps1
# Final, simplified version. This script uses direct calls to avoid all pathing and quote issues.

# --- Configuration ---
$pythonPath = ".\myenv_clean\Scripts\python.exe"
$configTuningDir = ".\config_tuning"

# --- Launch Sequence ---

# 0. Set Bybit Leverage
Write-Host "[INFO] Setting Bybit leverage levels from config file..."
$setLeverageArgs = "-Command `"`"cd '$configTuningDir'; & '$pythonPath' .\set_leverage.py`"`""
Start-Process powershell.exe -ArgumentList $setLeverageArgs -Wait
Write-Host "[INFO] Leverage setting process complete. Waiting 5 seconds..."
Start-Sleep -Seconds 5

# 1. Launch the Helios Server
Write-Host "[INFO] Launching the Helios Central Server in a new window..."
$heliosArgs = "-NoExit -Command `"`"cd '.\Trendline_Detectory'; & '$pythonPath' .\helios_server.py`"`""
Start-Process powershell.exe -ArgumentList $heliosArgs
Write-Host "[INFO] Helios Server launched. Waiting 15 seconds for it to initialize..."
Start-Sleep -Seconds 15

# 2. Launch the Aegis Risk Manager
Write-Host "[INFO] Launching the Aegis Risk Manager in a new window..."
$rmArgs = "-NoExit -Command `"`"cd '.\Trendline_Detectory\eyes_of_horus'; & '$pythonPath' .\main.py --live`"`""
Start-Process powershell.exe -ArgumentList $rmArgs
Write-Host "[INFO] Risk Manager launched. Waiting 10 seconds for it to initialize..."
Start-Sleep -Seconds 10

# 3. Launch the Arsenal Bots
Write-Host "[INFO] Launching all symbol bots in separate terminal windows..."

$botWorkingDir = ".\Trendline_Detectory"

foreach ($symbol in @("ETHUSDT", "BTCUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "LINKUSDT")) {
    Write-Host "   -> Launching $symbol..."

    $botArgs = "-NoExit -Command `"`"cd '$botWorkingDir'; & '$pythonPath' .\live_arsenal_horus_integrated.py --live --symbol $symbol`"`""

    Start-Process powershell.exe -ArgumentList $botArgs

    Start-Sleep -Seconds 5
}

Write-Host "[SUCCESS] All bots launched successfully in separate windows."
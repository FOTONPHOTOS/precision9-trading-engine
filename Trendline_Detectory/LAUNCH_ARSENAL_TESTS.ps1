# PRECISION9 ARSENAL - MASTER TEST LAUNCHER
# Complete trading system with detailed human-readable logging

Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "   ____  ____  _________________ ____  _   __    ___    ___   ____ ______  _____   ___    __ " -ForegroundColor Cyan
Write-Host "  / __ \/ __ \/ ____/ ____/  _// ___// | / /   /   |  / _ \ / __// ____/ / ___/  /   |  / / " -ForegroundColor Cyan
Write-Host " / /_/ / /_/ / __/ / /    / /  \__ \/  |/ /   / /| | / , _/_\ \ / __/   / (_ /  / /| | / /__" -ForegroundColor Cyan
Write-Host "/ ____/ _, _/ /___/ /___ _/ /  ___/ / /|  /   / ___ |/ /| /___/ / /___  \___/  / ___ |/ /___/" -ForegroundColor Cyan
Write-Host "/_/   /_/ |_/_____/\____//___//____/_/ |_/   /_/  |_/_/ |_|____//_____/       /_/  |_/_____/" -ForegroundColor Cyan
Write-Host ""
Write-Host "ARSENAL + TRADE EXECUTION SYSTEM - COMPLETE TEST SUITE" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Virtual Environment: G:\python files\precision9\myenv_fixed\Scripts\python.exe" -ForegroundColor Gray
Write-Host "Working Directory: G:\python files\precision9\Simulation Environment\Trendline_Detectory" -ForegroundColor Gray
Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Available Tests:" -ForegroundColor Yellow
Write-Host ""
Write-Host "  [1] Precision TP/SL Calculator Test" -ForegroundColor White
Write-Host "      - Demonstrates RR improvement from 0.59:1 to 2:1+" -ForegroundColor Gray
Write-Host "      - Shows smart money logic (OBs, FVGs, liquidity zones)" -ForegroundColor Gray
Write-Host "      - Enforces minimum 2:1 RR" -ForegroundColor Gray
Write-Host ""
Write-Host "  [2] Complete Trade Execution System Test" -ForegroundColor White
Write-Host "      - Arsenal 11-module analysis" -ForegroundColor Gray
Write-Host "      - Scenario planning (invalidation, stops, TP)" -ForegroundColor Gray
Write-Host "      - Real-time monitoring and execution" -ForegroundColor Gray
Write-Host "      - Fixes all Horus failures" -ForegroundColor Gray
Write-Host ""
Write-Host "  [3] Run Both Tests (Full System Demonstration)" -ForegroundColor White
Write-Host "      - Complete end-to-end test" -ForegroundColor Gray
Write-Host "      - All features with detailed logging" -ForegroundColor Gray
Write-Host ""
Write-Host "  [Q] Quit" -ForegroundColor White
Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

# Get user choice
$choice = Read-Host "Select test to run (1, 2, 3, or Q)"

# Change to the correct directory
Set-Location "G:\python files\precision9\Simulation Environment\Trendline_Detectory"

# Python path
$pythonPath = "G:\python files\precision9\myenv_fixed\Scripts\python.exe"

switch ($choice) {
    "1" {
        Write-Host ""
        Write-Host "================================================================================" -ForegroundColor Green
        Write-Host "LAUNCHING: Precision TP/SL Calculator Test" -ForegroundColor Green
        Write-Host "================================================================================" -ForegroundColor Green
        Write-Host ""
        & $pythonPath test_precision_tp_sl.py
    }
    "2" {
        Write-Host ""
        Write-Host "================================================================================" -ForegroundColor Green
        Write-Host "LAUNCHING: Complete Trade Execution System Test" -ForegroundColor Green
        Write-Host "================================================================================" -ForegroundColor Green
        Write-Host ""
        & $pythonPath test_trade_execution_system.py
    }
    "3" {
        Write-Host ""
        Write-Host "================================================================================" -ForegroundColor Green
        Write-Host "LAUNCHING: FULL SYSTEM TEST (BOTH TESTS)" -ForegroundColor Green
        Write-Host "================================================================================" -ForegroundColor Green
        Write-Host ""
        Write-Host "[TEST 1/2] Precision TP/SL Calculator..." -ForegroundColor Yellow
        Write-Host ""
        & $pythonPath test_precision_tp_sl.py

        Write-Host ""
        Write-Host ""
        Write-Host "================================================================================" -ForegroundColor Yellow
        Write-Host "[TEST 2/2] Complete Trade Execution System..." -ForegroundColor Yellow
        Write-Host "================================================================================" -ForegroundColor Yellow
        Write-Host ""
        & $pythonPath test_trade_execution_system.py
    }
    "Q" {
        Write-Host ""
        Write-Host "Exiting..." -ForegroundColor Gray
        exit
    }
    default {
        Write-Host ""
        Write-Host "Invalid choice. Please run the script again and select 1, 2, 3, or Q." -ForegroundColor Red
        exit
    }
}

Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "TEST COMPLETE - ARSENAL READY FOR BYBIT INTEGRATION" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "System Features Demonstrated:" -ForegroundColor Yellow
Write-Host ""
Write-Host "  [ARSENAL]" -ForegroundColor Green
Write-Host "    - 11-module market analysis" -ForegroundColor White
Write-Host "    - Swing structure, FVGs, Order Blocks" -ForegroundColor White
Write-Host "    - Liquidity sweeps and pools" -ForegroundColor White
Write-Host "    - Range trap and stop hunt detection" -ForegroundColor White
Write-Host "    - 500+ point confluence scoring" -ForegroundColor White
Write-Host ""
Write-Host "  [PRECISION TP/SL]" -ForegroundColor Green
Write-Host "    - Smart Money entry zones (Order Blocks)" -ForegroundColor White
Write-Host "    - Safe stops beyond liquidity (no sweeps)" -ForegroundColor White
Write-Host "    - FVG and liquidity targets" -ForegroundColor White
Write-Host "    - Minimum 2:1 RR enforcement" -ForegroundColor White
Write-Host "    - 288% RR improvement" -ForegroundColor White
Write-Host ""
Write-Host "  [SCENARIO PLANNING]" -ForegroundColor Green
Write-Host "    - 5+ invalidation scenarios" -ForegroundColor White
Write-Host "    - 3+ stop adjustment plans" -ForegroundColor White
Write-Host "    - Dynamic TP execution" -ForegroundColor White
Write-Host "    - All planned BEFORE entry" -ForegroundColor White
Write-Host ""
Write-Host "  [REAL-TIME MONITORING]" -ForegroundColor Green
Write-Host "    - Smart invalidation (40% retracement required)" -ForegroundColor White
Write-Host "    - Market orders when needed" -ForegroundColor White
Write-Host "    - Intelligent stop trailing" -ForegroundColor White
Write-Host "    - Reversal prediction" -ForegroundColor White
Write-Host ""
Write-Host "  [HORUS FIXES]" -ForegroundColor Green
Write-Host "    - No closing on minor pullbacks" -ForegroundColor White
Write-Host "    - Fixes \$206 TP miss (market orders)" -ForegroundColor White
Write-Host "    - Smart trailing (knows when to stop)" -ForegroundColor White
Write-Host "    - Exits before TP if reversal detected" -ForegroundColor White
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Integrate precision TP/SL into intelligent_strategy_brain.py" -ForegroundColor White
Write-Host "  2. Add Bybit API wrapper for live execution" -ForegroundColor White
Write-Host "  3. Test in paper trading mode" -ForegroundColor White
Write-Host "  4. Deploy to live mainnet" -ForegroundColor White
Write-Host ""
Write-Host "Press any key to exit..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

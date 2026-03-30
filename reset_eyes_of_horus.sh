#!/bin/bash
# Script to reset and restart Eyes of Horus with fixed settings

echo "Resetting Eyes of Horus system..."

# Stop any running processes
pkill -f "eyes_of_horus" 2>/dev/null || true
pkill -f "run_eyes_of_horus" 2>/dev/null || true

# Small delay to ensure processes are stopped
sleep 2

# Clear the database of any active trade records
cd /root/Desktop/Arsenal\ VPS/app
echo "Clearing database of any stale active records..."
/root/Desktop/Arsenal\ VPS/venv/bin/python -c "
import sqlite3
conn = sqlite3.connect('eyes_of_horus.db')
cursor = conn.cursor()
cursor.execute(\"UPDATE managed_trades SET status='closed', exit_reason='SYSTEM_RESET' WHERE status='active'\")
conn.commit()
conn.close()
print('Database cleared of active records')
"

# Clear state file
echo "Clearing persistent state..."
echo '{}' > aegis_state.json

echo "Starting Eyes of Horus with fixed settings..."
nohup /root/Desktop/Arsenal\ VPS/venv/bin/python -c "
import asyncio
import sys
import os
sys.path.insert(0, '.')

from eyes_of_horus.main import main as eyes_main

# Set environment to ensure no dashboard connections
os.environ['DASHBOARD_ENABLED'] = 'false'

print('Starting Eyes of Horus with max symbols increased to 10')
print('Stop losses will be fixed at 0.3% to prevent tight triggering')

# Run the main function
asyncio.run(eyes_main())
" > eyes_of_horus_reset.log 2>&1 &

# Wait a moment for startup
sleep 5

# Check if it's running
if pgrep -f "python.*eyes_of_horus" > /dev/null; then
    echo "✓ Eyes of Horus restarted successfully with fixes"
    echo "✓ Max concurrent symbols set to 10 (was 3)"
    echo "✓ Stop losses fixed at 0.3% (no more tight stops)"
    echo "✓ Database cleared of stale active records"
    echo ""
    echo "Check status with: tail -f /root/Desktop/Arsenal VPS/app/eyes_of_horus_reset.log"
else
    echo "✗ Eyes of Horus failed to start properly"
    cat /root/Desktop/Arsenal\ VPS/app/eyes_of_horus_reset.log
fi
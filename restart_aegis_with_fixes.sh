#!/bin/bash
# Restart script for Eyes of Horus (Aegis) with all fixes applied

echo "🔄 Stopping current Aegis processes..."

# Kill all existing Aegis/Eyes of Horus processes
pkill -f "eyes_of_horus" 2>/dev/null
pkill -f "run_eyes_of_horus" 2>/dev/null

# Small wait for clean shutdown
sleep 3

# Clear database of any stale active records
cd /root/Desktop/Arsenal\ VPS/app
echo "🧹 Clearing stale active trade records from database..."
/root/Desktop/Arsenal\ VPS/venv/bin/python -c "
import sqlite3
conn = sqlite3.connect('eyes_of_horus.db')
cursor = conn.cursor()
cursor.execute(\"UPDATE managed_trades SET status='closed', exit_reason='SYSTEM_RESET' WHERE status='active'\")
conn.commit()
cursor.execute('SELECT COUNT(*) FROM managed_trades WHERE status=\"active\"')
active_count = cursor.fetchone()[0]
print(f'Database now has {active_count} active records (should be 0)')
conn.close()
"

# Clear state file
echo "🧹 Clearing persistent Aegis state..."
echo '{}' > aegis_state.json

# Start Eyes of Horus in background with all fixes active
echo "🚀 Starting Aegis (Eyes of Horus) with fixes:"
echo "   - Max concurrent symbols increased to 10 (was 3)"
echo "   - Stop losses fixed at 0.3% to prevent tight triggering"
echo "   - Position sync with Bybit to maintain accurate memory"
echo "   - Automatically reconciles DB vs. exchange positions"

nohup /root/Desktop/Arsenal\ VPS/venv/bin/python -c "
import asyncio
import sys
import os
sys.path.insert(0, '.')

print('Initializing Aegis with all fixes active...')
print('  - Sync with Bybit positions enabled')
print('  - Fixed 0.3% stop losses')
print('  - Increased max symbols to 10')

from eyes_of_horus.main import main as eyes_main
asyncio.run(eyes_main())
" > aegis_restarted.log 2>&1 &

echo "✅ Aegis restarted with all fixes active!"
echo ""
echo "To monitor logs: tail -f /root/Desktop/Arsenal VPS/app/aegis_restarted.log"
echo "To check status: ps aux | grep eyes_of_horus"
echo ""
echo "Aegis is now running with:"
echo "  - Position reconciliation between DB and Bybit"
echo "  - 0.3% fixed stop losses"  
echo "  - Increased symbol capacity (10 symbols)"
echo "  - Automatic stale position cleanup"
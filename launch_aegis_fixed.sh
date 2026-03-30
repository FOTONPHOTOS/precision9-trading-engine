#!/bin/bash

# Aegis (Eyes of Horus) Launch Script with Database Cleanup
# This script starts Aegis with proper synchronization and clears any stale records

echo " Starting Aegis (Eyes of Horus) with synchronization fix..."

cd /root/Desktop/Arsenal\ VPS/app

echo " Clearing any stale trade records from database..."
/root/Desktop/Arsenal\ VPS/venv/bin/python -c "
import sqlite3
conn = sqlite3.connect('eyes_of_horus.db')
cursor = conn.cursor()
cursor.execute(\"UPDATE managed_trades SET status='closed', exit_reason='SYSTEM_LAUNCH_CLEANUP' WHERE status='active'\")
conn.commit()
rows_affected = cursor.rowcount
conn.close()
print(f'Cleared {rows_affected} stale active trade records from database')
"

echo " Database cleanup complete"
echo " Starting Aegis with fixed synchronization..."
echo " Position synchronization will keep database accurate with Bybit"

# Start Aegis in the foreground so you can see it run
/root/Desktop/Arsenal\ VPS/venv/bin/python -c "
import asyncio
import sys
sys.path.insert(0, '.')

from eyes_of_horus.main import main as eyes_main
print('Starting Aegis (Eyes of Horus)...')
print('Position synchronization will keep database accurate with Bybit')

asyncio.run(eyes_main())
"
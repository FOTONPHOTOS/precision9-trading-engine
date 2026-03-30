# timezone_utils.py

from datetime import datetime, time
from zoneinfo import ZoneInfo

# --- Universal Time Function ---

def get_utc_now() -> datetime:
    """
    Returns a timezone-aware datetime object in UTC.

    This should be used for ALL timestamping purposes across the application
    to ensure timezone independence.
    """
    return datetime.now(ZoneInfo("UTC"))

# --- Market Session Definitions (in UTC) ---

# Note: These are general times and do not account for DST shifts in all regions.
# For high-precision session trading, a more advanced library might be needed,
# but this provides a robust, standardized baseline.

SESSIONS = {
    "ASIA": {
        "start": time(0, 0, tzinfo=ZoneInfo("UTC")),   # 00:00 UTC
        "end": time(9, 0, tzinfo=ZoneInfo("UTC")),     # 09:00 UTC
        "name": "Asia"
    },
    "LONDON": {
        "start": time(7, 0, tzinfo=ZoneInfo("UTC")),   # 07:00 UTC
        "end": time(16, 0, tzinfo=ZoneInfo("UTC")),    # 16:00 UTC
        "name": "London"
    },
    "NEW_YORK": {
        "start": time(13, 0, tzinfo=ZoneInfo("UTC")),  # 13:00 UTC
        "end": time(22, 0, tzinfo=ZoneInfo("UTC")),    # 22:00 UTC
        "name": "New York"
    }
}

def get_current_session() -> dict:
    """
    Determines the current major trading session based on UTC time.
    Accounts for overlaps.
    """
    now_utc = get_utc_now().time()
    
    active_sessions = []
    
    if SESSIONS["ASIA"]["start"] <= now_utc < SESSIONS["ASIA"]["end"]:
        active_sessions.append(SESSIONS["ASIA"]["name"])
        
    if SESSIONS["LONDON"]["start"] <= now_utc < SESSIONS["LONDON"]["end"]:
        active_sessions.append(SESSIONS["LONDON"]["name"])

    if SESSIONS["NEW_YORK"]["start"] <= now_utc < SESSIONS["NEW_YORK"]["end"]:
        active_sessions.append(SESSIONS["NEW_YORK"]["name"])

    if not active_sessions:
        return {"name": "Inter-Session", "active_sessions": []}

    return {"name": " / ".join(active_sessions), "active_sessions": active_sessions}

if __name__ == '__main__':
    now = get_utc_now()
    current_session = get_current_session()
    print(f"Current UTC time: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"Current Session: {current_session['name']}")


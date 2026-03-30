
import pytz
from datetime import datetime

# Define session times in UTC
ASIAN_SESSION_START = 0  # 00:00 UTC
ASIAN_SESSION_END = 9    # 09:00 UTC
LONDON_SESSION_START = 7 # 07:00 UTC
LONDON_SESSION_END = 16  # 16:00 UTC
NEW_YORK_SESSION_START = 12 # 12:00 UTC
NEW_YORK_SESSION_END = 21   # 21:00 UTC

def get_current_session():
    """
    Determines the current trading session(s) based on UTC time.
    Accounts for overlaps.
    """
    now_utc = datetime.utcnow()
    current_hour = now_utc.hour
    sessions = []

    if ASIAN_SESSION_START <= current_hour < ASIAN_SESSION_END:
        sessions.append("asian")
    if LONDON_SESSION_START <= current_hour < LONDON_SESSION_END:
        sessions.append("london")
    if NEW_YORK_SESSION_START <= current_hour < NEW_YORK_SESSION_END:
        sessions.append("new_york")

    if not sessions:
        return "inter-session"

    # Handle overlaps specifically if needed, otherwise just return all active
    return "_".join(sessions)

def is_asian_session():
    """
    Returns True if the current time is within the Asian session hours.
    """
    current_session = get_current_session()
    return "asian" in current_session and "london" not in current_session

def is_london_or_ny_session():
    """
    Returns True if the current time is within London or New York sessions.
    """
    current_session = get_current_session()
    return "london" in current_session or "new_york" in current_session

def is_session_transition_blackout(blackout_minutes: int = 30):
    """
    Checks if the current time is within a blackout period around session starts and ends.
    The blackout period is `blackout_minutes` before and after the session transition.
    """
    now_utc = datetime.utcnow()
    current_time = now_utc.hour * 60 + now_utc.minute

    sessions = {
        "asian": (ASIAN_SESSION_START, ASIAN_SESSION_END),
        "london": (LONDON_SESSION_START, LONDON_SESSION_END),
        "new_york": (NEW_YORK_SESSION_START, NEW_YORK_SESSION_END),
    }

    for session_name, (start_hour, end_hour) in sessions.items():
        start_time_minutes = start_hour * 60
        end_time_minutes = end_hour * 60

        # Blackout for session start
        start_blackout_begin = (start_time_minutes - blackout_minutes + 1440) % 1440
        start_blackout_end = (start_time_minutes + blackout_minutes) % 1440

        # Blackout for session end
        end_blackout_begin = (end_time_minutes - blackout_minutes + 1440) % 1440
        end_blackout_end = (end_time_minutes + blackout_minutes) % 1440
        
        # Handle overnight transition for Asian session start
        if session_name == "asian" and start_hour == 0:
             if current_time >= start_blackout_begin or current_time < start_blackout_end:
                return True
        else:
            if start_blackout_begin <= current_time < start_blackout_end:
                return True

        if end_blackout_begin <= current_time < end_blackout_end:
            return True

    return False

if __name__ == '__main__':
    # Example of how to use it
    session = get_current_session()
    print(f"Current time (UTC): {datetime.utcnow().strftime('%H:%M:%S')}")
    print(f"Current trading session(s): {session}")
    print(f"Is it Asian session (exclusive)? {is_asian_session()}")
    print(f"Is it London or NY session? {is_london_or_ny_session()}")
    print(f"Is it session transition blackout? {is_session_transition_blackout()}")


from datetime import date

import db

DAILY_LIMIT = 40  # AI calls per day across all visitors


def allow_call():
    key = f"ai_calls_{date.today().isoformat()}"
    used = int(db.get_setting(key, "0"))
    if used >= DAILY_LIMIT:
        return False
    db.set_setting(key, used + 1)
    return True
"""Late fee calculation rules for tool library loans.

All amounts are in integer paise (1 Rupee = 100 paise).
"""

import math
from datetime import datetime

from app.core.clock import ensure_utc

# Financial and business constants in integer paise
DAILY_LATE_FEE_PAISE = 1000  # ₹10 per 24-hour period (calendar day rounded up)
MAX_LATE_FEE_PAISE = 20000  # ₹200 maximum cap per loan
SECONDS_PER_DAY = 86400


def calculate_late_fee(
    return_time: datetime,
    due_at: datetime,
    replacement_value: int,
) -> int:
    """Calculate the late fee for an overdue loan.

    Rules:
    - 0 fee if returned at or before due_at.
    - Elapsed time past due_at is divided into 24-hour intervals and rounded up:
      * 1 second late = 1 day = ₹10 (1,000 paise).
      * Exactly 24 hours late = 1 day = ₹10 (1,000 paise).
      * 24 hours and 1 second late = 2 days = ₹20 (2,000 paise).
    - Capped at ₹200 (20,000 paise).
    - Never exceeds the item's replacement value (in paise).
    """
    ret_utc = ensure_utc(return_time)
    due_utc = ensure_utc(due_at)
    if ret_utc is None or due_utc is None:
        return 0

    elapsed_seconds = (ret_utc - due_utc).total_seconds()
    if elapsed_seconds <= 0:
        return 0

    days_overdue = math.ceil(elapsed_seconds / SECONDS_PER_DAY)
    uncapped_fee = days_overdue * DAILY_LATE_FEE_PAISE
    capped_fee = min(uncapped_fee, MAX_LATE_FEE_PAISE)
    return min(capped_fee, max(0, replacement_value))

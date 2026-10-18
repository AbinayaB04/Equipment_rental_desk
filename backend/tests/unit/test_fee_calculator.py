"""Unit tests for the pure late-fee calculation logic."""

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.fee_calculator import (
    DAILY_LATE_FEE_PAISE,
    MAX_LATE_FEE_PAISE,
    calculate_late_fee,
)


@pytest.fixture
def base_time() -> datetime:
    return datetime(2026, 10, 17, 12, 0, 0, tzinfo=UTC)


def test_fee_is_zero_when_returned_on_or_before_due_date(base_time: datetime):
    due_at = base_time
    # Returned 1 hour early
    assert calculate_late_fee(due_at - timedelta(hours=1), due_at, replacement_value=50000) == 0
    # Returned exactly at due_at (0 seconds overdue)
    assert calculate_late_fee(due_at, due_at, replacement_value=50000) == 0


def test_fee_boundary_first_second_and_day_one(base_time: datetime):
    due_at = base_time
    # 1 second overdue -> 1st day (1,000 paise = ₹10)
    assert (
        calculate_late_fee(due_at + timedelta(seconds=1), due_at, replacement_value=50000)
        == DAILY_LATE_FEE_PAISE
    )
    # 12 hours overdue -> still 1st day (1,000 paise = ₹10)
    assert (
        calculate_late_fee(due_at + timedelta(hours=12), due_at, replacement_value=50000)
        == DAILY_LATE_FEE_PAISE
    )
    # 23 hours 59 minutes 59 seconds -> still 1st day (1,000 paise = ₹10)
    assert (
        calculate_late_fee(
            due_at + timedelta(hours=23, minutes=59, seconds=59),
            due_at,
            replacement_value=50000,
        )
        == DAILY_LATE_FEE_PAISE
    )
    # Exactly 24 hours overdue -> 1st day (1,000 paise = ₹10)
    assert (
        calculate_late_fee(due_at + timedelta(hours=24), due_at, replacement_value=50000)
        == DAILY_LATE_FEE_PAISE
    )


def test_fee_boundary_day_two_transition(base_time: datetime):
    due_at = base_time
    # 24 hours and 1 second overdue -> 2nd day (2,000 paise = ₹20)
    assert (
        calculate_late_fee(
            due_at + timedelta(hours=24, seconds=1),
            due_at,
            replacement_value=50000,
        )
        == 2000
    )
    # Exactly 48 hours overdue -> 2nd day (2,000 paise = ₹20)
    assert calculate_late_fee(due_at + timedelta(hours=48), due_at, replacement_value=50000) == 2000
    # 48 hours and 1 second overdue -> 3rd day (3,000 paise = ₹30)
    assert (
        calculate_late_fee(
            due_at + timedelta(hours=48, seconds=1),
            due_at,
            replacement_value=50000,
        )
        == 3000
    )


def test_fee_capped_at_200_rupees(base_time: datetime):
    due_at = base_time
    # 19 days overdue on ₹1,000 item -> 19 * ₹10 = ₹190 (19,000 paise)
    assert (
        calculate_late_fee(due_at + timedelta(days=19), due_at, replacement_value=100000) == 19000
    )
    # 20 days overdue on ₹1,000 item -> exactly ₹200 (20,000 paise)
    assert (
        calculate_late_fee(due_at + timedelta(days=20), due_at, replacement_value=100000)
        == MAX_LATE_FEE_PAISE
    )
    # 21 days overdue on ₹1,000 item -> capped at ₹200 (20,000 paise)
    assert (
        calculate_late_fee(due_at + timedelta(days=21), due_at, replacement_value=100000)
        == MAX_LATE_FEE_PAISE
    )
    # 60 days overdue on ₹1,000 item -> still capped at ₹200 (20,000 paise)
    assert (
        calculate_late_fee(due_at + timedelta(days=60), due_at, replacement_value=100000)
        == MAX_LATE_FEE_PAISE
    )


def test_fee_capped_at_replacement_value_when_less_than_200(base_time: datetime):
    due_at = base_time
    # Item with replacement value of ₹150 (15,000 paise)
    replacement_value = 15000

    # 10 days overdue -> ₹100 (10,000 paise), under both caps
    assert calculate_late_fee(due_at + timedelta(days=10), due_at, replacement_value) == 10000
    # 15 days overdue -> exactly ₹150 (15,000 paise)
    assert calculate_late_fee(due_at + timedelta(days=15), due_at, replacement_value) == 15000
    # 25 days overdue -> would be ₹250 uncapped, ₹200 under max cap, but capped at ₹150 replacement
    assert calculate_late_fee(due_at + timedelta(days=25), due_at, replacement_value) == 15000


def test_fee_capped_at_replacement_value_low_value_item(base_time: datetime):
    due_at = base_time
    # Small item with replacement value of ₹35 (3,500 paise)
    replacement_value = 3500

    # 1 day overdue -> ₹10 (1,000 paise)
    assert calculate_late_fee(due_at + timedelta(days=1), due_at, replacement_value) == 1000
    # 3 days overdue -> ₹30 (3,000 paise)
    assert calculate_late_fee(due_at + timedelta(days=3), due_at, replacement_value) == 3000
    # 4 days overdue -> 4 * 10 = ₹40 > ₹35, capped at ₹35 (3,500 paise)
    assert calculate_late_fee(due_at + timedelta(days=4), due_at, replacement_value) == 3500

"""Unit tests for pure borrowing eligibility assessment."""

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.eligibility import (
    LONG_OVERDUE_DAYS_THRESHOLD,
    MAX_ACTIVE_LOANS,
    MAX_ELIGIBLE_BALANCE_PAISE,
    assert_borrow_eligible,
    assess_borrow_eligibility,
)
from app.domain.exceptions import (
    ActiveLoanLimitExceededError,
    MemberBalanceBlockError,
    MemberOverdueBlockError,
    MemberSuspendedError,
)
from app.models.loan import Loan, LoanStatus
from app.models.member import Member, MemberStatus


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 10, 17, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def active_member(now: datetime) -> Member:
    return Member(
        id=1,
        name="Eligible Member",
        phone="+91-99999-00001",
        join_date=now - timedelta(days=30),
        status=MemberStatus.ACTIVE,
        running_fee_balance=0,
    )


def test_clean_active_member_is_eligible(active_member: Member, now: datetime):
    res = assess_borrow_eligibility(active_member, active_loans=[], now=now)
    assert res.is_eligible is True
    assert len(res.reasons) == 0
    # assert_borrow_eligible should not raise
    assert_borrow_eligible(active_member, active_loans=[], now=now)


def test_suspended_member_is_blocked(active_member: Member, now: datetime):
    active_member.status = MemberStatus.SUSPENDED
    res = assess_borrow_eligibility(active_member, active_loans=[], now=now)
    assert res.is_eligible is False
    assert "suspended" in res.reasons[0].lower()

    with pytest.raises(MemberSuspendedError):
        assert_borrow_eligible(active_member, active_loans=[], now=now)


def test_balance_boundary_eligibility(active_member: Member, now: datetime):
    # Exactly ₹100 (10,000 paise) -> ELIGIBLE
    active_member.running_fee_balance = MAX_ELIGIBLE_BALANCE_PAISE
    res = assess_borrow_eligibility(active_member, active_loans=[], now=now)
    assert res.is_eligible is True
    assert_borrow_eligible(active_member, active_loans=[], now=now)

    # ₹100.01 (10,001 paise) -> BLOCKED
    active_member.running_fee_balance = MAX_ELIGIBLE_BALANCE_PAISE + 1
    res = assess_borrow_eligibility(active_member, active_loans=[], now=now)
    assert res.is_eligible is False
    assert "limit" in res.reasons[0].lower()

    with pytest.raises(MemberBalanceBlockError):
        assert_borrow_eligible(active_member, active_loans=[], now=now)


def test_active_loans_limit_boundary(active_member: Member, now: datetime):
    # 2 active loans -> ELIGIBLE
    loans_2 = [
        Loan(id=1, member_id=1, item_id=1, status=LoanStatus.CHECKED_OUT, reserved_at=now),
        Loan(id=2, member_id=1, item_id=2, status=LoanStatus.RESERVED, reserved_at=now),
    ]
    res = assess_borrow_eligibility(active_member, active_loans=loans_2, now=now)
    assert res.is_eligible is True
    assert_borrow_eligible(active_member, active_loans=loans_2, now=now)

    # 3 active loans -> BLOCKED (at 3-loan limit, cannot take a 4th)
    loans_3 = loans_2 + [
        Loan(id=3, member_id=1, item_id=3, status=LoanStatus.CHECKED_OUT, reserved_at=now)
    ]
    assert len(loans_3) == MAX_ACTIVE_LOANS
    res = assess_borrow_eligibility(active_member, active_loans=loans_3, now=now)
    assert res.is_eligible is False
    assert "limit" in res.reasons[0].lower()

    with pytest.raises(ActiveLoanLimitExceededError):
        assert_borrow_eligible(active_member, active_loans=loans_3, now=now)


def test_long_overdue_14_day_boundary(active_member: Member, now: datetime):
    # Loan overdue by 13 days -> ELIGIBLE
    loan_13d = Loan(
        id=1,
        member_id=1,
        item_id=1,
        status=LoanStatus.CHECKED_OUT,
        reserved_at=now - timedelta(days=20),
        checked_out_at=now - timedelta(days=20),
        due_at=now - timedelta(days=13),
    )
    res = assess_borrow_eligibility(active_member, active_loans=[loan_13d], now=now)
    assert res.is_eligible is True
    assert_borrow_eligible(active_member, active_loans=[loan_13d], now=now)

    # Loan overdue by exactly 14 days -> ELIGIBLE (rule: > 14 days blocks)
    loan_exact_14d = Loan(
        id=2,
        member_id=1,
        item_id=2,
        status=LoanStatus.CHECKED_OUT,
        reserved_at=now - timedelta(days=21),
        checked_out_at=now - timedelta(days=21),
        due_at=now - timedelta(days=LONG_OVERDUE_DAYS_THRESHOLD),
    )
    res = assess_borrow_eligibility(active_member, active_loans=[loan_exact_14d], now=now)
    assert res.is_eligible is True
    assert_borrow_eligible(active_member, active_loans=[loan_exact_14d], now=now)

    # Loan overdue by 14 days and 1 second -> BLOCKED (> 14 days)
    loan_14d_plus = Loan(
        id=3,
        member_id=1,
        item_id=3,
        status=LoanStatus.CHECKED_OUT,
        reserved_at=now - timedelta(days=22),
        checked_out_at=now - timedelta(days=22),
        due_at=now - timedelta(days=14, seconds=1),
    )
    res = assess_borrow_eligibility(active_member, active_loans=[loan_14d_plus], now=now)
    assert res.is_eligible is False
    assert "overdue" in res.reasons[0].lower()

    with pytest.raises(MemberOverdueBlockError):
        assert_borrow_eligible(active_member, active_loans=[loan_14d_plus], now=now)

"""Unit tests for MemberService application logic."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.domain.exceptions import (
    EntityNotFoundError,
    InvalidPaymentAmountError,
    MemberBalanceBlockError,
    MemberSuspendedError,
    OverpaymentError,
)
from app.models.item import Item
from app.models.loan import Loan, LoanStatus
from app.models.member import Member, MemberStatus
from app.services.member_service import MemberService


def test_suspend_and_reinstate_member(session: Session):
    """MemberService can suspend an active member and reinstate a suspended member."""
    now = datetime(2026, 10, 15, 10, 0, 0, tzinfo=UTC)
    member = Member(name="Bob", phone="+91-98765-43211", join_date=now)
    session.add(member)
    session.flush()

    assert member.status == MemberStatus.ACTIVE

    MemberService.suspend_member(session, member.id)
    assert member.status == MemberStatus.SUSPENDED

    # Asserting eligibility raises
    with pytest.raises(MemberSuspendedError):
        MemberService.assert_eligible(session, member.id, now=now)

    MemberService.reinstate_member(session, member.id)
    assert member.status == MemberStatus.ACTIVE

    # Asserting eligibility succeeds
    MemberService.assert_eligible(session, member.id, now=now)


def test_record_payment_normal_and_exact_payoff(session: Session):
    """Recording valid payments reduces running_fee_balance and creates Payment records."""
    now = datetime(2026, 10, 15, 10, 0, 0, tzinfo=UTC)
    member = Member(
        name="Alice",
        phone="+91-98765-43210",
        join_date=now,
        running_fee_balance=5000,  # ₹50
    )
    session.add(member)
    session.flush()

    # Partial payment ₹20 (2000 paise)
    p1 = MemberService.record_payment(
        session, member_id=member.id, amount=2000, note="Partial fee payment", now=now
    )
    assert p1.amount == 2000
    assert p1.note == "Partial fee payment"
    assert member.running_fee_balance == 3000

    # Payoff remaining ₹30 (3000 paise)
    p2 = MemberService.record_payment(
        session,
        member_id=member.id,
        amount=3000,
        note="Remaining payoff",
        now=now + timedelta(hours=1),
    )
    assert p2.amount == 3000
    assert member.running_fee_balance == 0


def test_record_payment_non_positive_amount_rejected(session: Session):
    """Payment amount <= 0 raises InvalidPaymentAmountError."""
    now = datetime(2026, 10, 15, 10, 0, 0, tzinfo=UTC)
    member = Member(
        name="Alice",
        phone="+91-98765-43210",
        join_date=now,
        running_fee_balance=5000,
    )
    session.add(member)
    session.flush()

    with pytest.raises(InvalidPaymentAmountError):
        MemberService.record_payment(session, member_id=member.id, amount=0, now=now)

    with pytest.raises(InvalidPaymentAmountError):
        MemberService.record_payment(session, member_id=member.id, amount=-1000, now=now)


def test_record_payment_overpayment_rejected(session: Session):
    """Paying more than outstanding running_fee_balance raises OverpaymentError."""
    now = datetime(2026, 10, 15, 10, 0, 0, tzinfo=UTC)
    member = Member(
        name="Alice",
        phone="+91-98765-43210",
        join_date=now,
        running_fee_balance=2000,  # ₹20
    )
    session.add(member)
    session.flush()

    with pytest.raises(OverpaymentError) as exc_info:
        MemberService.record_payment(
            session,
            member_id=member.id,
            amount=2500,
            now=now,  # ₹25
        )
    assert "exceeds outstanding balance" in str(exc_info.value)
    # Balance remains unchanged
    assert member.running_fee_balance == 2000


def test_record_payment_nonexistent_member_raises(session: Session):
    """Paying for nonexistent member raises EntityNotFoundError."""
    with pytest.raises(EntityNotFoundError):
        MemberService.record_payment(session, member_id=999, amount=1000)


def test_get_active_loans_excludes_expired_reservations(session: Session):
    """Reservations >= 48 hours old do not count toward active loans."""
    res_time = datetime(2026, 10, 15, 10, 0, 0, tzinfo=UTC)
    member = Member(name="Alice", phone="+91-98765-43210", join_date=res_time)
    items = [Item(name=f"Tool {i}", category="Tools", replacement_value=10000) for i in range(1, 4)]
    session.add(member)
    session.add_all(items)
    session.flush()

    # Loan 1: active reservation made 10h ago
    loan1 = Loan(
        member_id=member.id,
        item_id=items[0].id,
        status=LoanStatus.RESERVED,
        reserved_at=res_time,
    )
    # Loan 2: checked out
    loan2 = Loan(
        member_id=member.id,
        item_id=items[1].id,
        status=LoanStatus.CHECKED_OUT,
        reserved_at=res_time,
        checked_out_at=res_time + timedelta(hours=1),
        due_at=res_time + timedelta(days=7),
    )
    # Loan 3: reservation that is 50h old (expired)
    loan3 = Loan(
        member_id=member.id,
        item_id=items[2].id,
        status=LoanStatus.RESERVED,
        reserved_at=res_time - timedelta(hours=50),
    )
    session.add_all([loan1, loan2, loan3])
    session.flush()

    active = MemberService.get_active_loans(session, member.id, now=res_time)
    assert len(active) == 2
    active_ids = {loan.id for loan in active}
    assert loan1.id in active_ids
    assert loan2.id in active_ids
    assert loan3.id not in active_ids


def test_check_eligibility_returns_detailed_result(session: Session):
    """check_eligibility provides structured is_eligible and reasons tuple."""
    now = datetime(2026, 10, 15, 10, 0, 0, tzinfo=UTC)
    member = Member(
        name="Debtor",
        phone="+91-98765-43210",
        join_date=now,
        running_fee_balance=12000,  # ₹120 > ₹100 limit
    )
    session.add(member)
    session.flush()

    result = MemberService.check_eligibility(session, member.id, now=now)
    assert not result.is_eligible
    assert len(result.reasons) == 1
    assert "₹120.00" in result.primary_reason

    with pytest.raises(MemberBalanceBlockError):
        MemberService.assert_eligible(session, member.id, now=now)


def test_create_member_service(session: Session):
    """MemberService.create_member initializes an active member with zero balance."""
    now = datetime(2026, 10, 15, 10, 0, 0, tzinfo=UTC)
    member = MemberService.create_member(
        session, name=" Charlie Brown ", phone=" +91-98765-00003 ", now=now
    )

    assert member.id is not None
    assert member.name == "Charlie Brown"
    assert member.phone == "+91-98765-00003"
    assert member.status == MemberStatus.ACTIVE
    assert member.running_fee_balance == 0
    assert member.join_date == now

    # Blank name or phone rejected
    with pytest.raises(ValueError, match="name"):
        MemberService.create_member(session, name="  ", phone="+91-11111-11111")
    with pytest.raises(ValueError, match="phone"):
        MemberService.create_member(session, name="Valid Name", phone="   ")


def test_update_member_service(session: Session):
    """MemberService.update_member updates permitted profile fields."""
    now = datetime(2026, 10, 15, 10, 0, 0, tzinfo=UTC)
    member = MemberService.create_member(session, name="David", phone="+91-98765-00004", now=now)

    updated = MemberService.update_member(
        session, member.id, name="David Updated", phone="+91-98765-00005"
    )
    assert updated.name == "David Updated"
    assert updated.phone == "+91-98765-00005"
    assert updated.status == MemberStatus.ACTIVE
    assert updated.running_fee_balance == 0

    # Nonexistent member raises EntityNotFoundError
    with pytest.raises(EntityNotFoundError):
        MemberService.update_member(session, 99999, name="Ghost")


def test_list_members_service(session: Session):
    """MemberService.list_members supports status filtering and pagination."""
    now = datetime(2026, 10, 15, 10, 0, 0, tzinfo=UTC)
    m1 = MemberService.create_member(session, name="Member 1", phone="+91-1", now=now)
    m2 = MemberService.create_member(session, name="Member 2", phone="+91-2", now=now)
    MemberService.suspend_member(session, m2.id)

    all_members = MemberService.list_members(session)
    assert len(all_members) >= 2

    active_only = MemberService.list_members(session, status=MemberStatus.ACTIVE)
    assert any(m.id == m1.id for m in active_only)
    assert all(m.status == MemberStatus.ACTIVE for m in active_only)

    suspended_only = MemberService.list_members(session, status=MemberStatus.SUSPENDED)
    assert any(m.id == m2.id for m in suspended_only)
    assert all(m.status == MemberStatus.SUSPENDED for m in suspended_only)


def test_get_statement_service(session: Session):
    """MemberService.get_statement aggregates loans, payments, and fees correctly."""
    now = datetime(2026, 10, 15, 10, 0, 0, tzinfo=UTC)
    member = MemberService.create_member(
        session, name="Statement Member", phone="+91-99999", now=now
    )

    # 1. Nonexistent member raises EntityNotFoundError
    with pytest.raises(EntityNotFoundError):
        MemberService.get_statement(session, member_id=999999)

    # 2. Empty statement
    stmt = MemberService.get_statement(session, member_id=member.id)
    assert stmt["member_id"] == member.id
    assert stmt["loans"] == []
    assert stmt["payments"] == []
    assert stmt["total_fees_charged"] == 0
    assert stmt["total_payments_recorded"] == 0
    assert stmt["current_outstanding_balance"] == 0

    # 3. Add loans and payment
    from app.models.item import Item, ItemStatus
    from app.models.loan import Loan, LoanStatus

    item = Item(
        name="Drill X", category="Tools", replacement_value=10000, status=ItemStatus.AVAILABLE
    )
    session.add(item)
    session.flush()

    loan1 = Loan(
        member_id=member.id,
        item_id=item.id,
        status=LoanStatus.RETURNED,
        reserved_at=now,
        checked_out_at=now,
        due_at=now + timedelta(days=7),
        returned_at=now + timedelta(days=10),
        fee_charged=3000,
    )
    loan2 = Loan(
        member_id=member.id,
        item_id=item.id,
        status=LoanStatus.RESERVED,
        reserved_at=now + timedelta(days=1),
        fee_charged=0,
    )
    session.add_all([loan1, loan2])
    member.running_fee_balance = 3000
    session.flush()

    # Make a payment of 1000
    p1 = MemberService.record_payment(
        session, member_id=member.id, amount=1000, now=now + timedelta(days=10)
    )

    stmt2 = MemberService.get_statement(session, member_id=member.id)
    assert len(stmt2["loans"]) == 2
    # Newest loan first
    assert stmt2["loans"][0].id == loan2.id
    assert stmt2["loans"][1].id == loan1.id
    assert len(stmt2["payments"]) == 1
    assert stmt2["payments"][0].id == p1.id
    assert stmt2["total_fees_charged"] == 3000
    assert stmt2["total_payments_recorded"] == 1000
    assert stmt2["current_outstanding_balance"] == 2000

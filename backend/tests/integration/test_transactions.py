"""Integration tests verifying transaction boundaries, rollback, and expired checkout settlement.

Verifies:
1. Expired checkout in caller transactions leaves consistent states in fresh sessions.
2. Single-transaction outcome pattern safely commits expiry cleanup while returning failure.
3. Domain exceptions (e.g. ineligibility/overpayment) roll back all mutations atomically.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.domain.exceptions import MemberSuspendedError, OverpaymentError, ReservationExpiredError
from app.models.item import Item, ItemStatus
from app.models.loan import Loan, LoanStatus
from app.models.member import Member, MemberStatus
from app.models.payment import Payment
from app.services.loan_service import LoanService
from app.services.member_service import MemberService

pytestmark = pytest.mark.integration


def get_pg_engine():
    """Connect to PostgreSQL using the configured DATABASE_URL."""
    url = Settings.from_env().database_url
    if not url or "postgresql" not in url:
        return None
    try:
        engine = create_engine(url, pool_pre_ping=True)
        with engine.connect():
            pass
        return engine
    except Exception:
        return None


@pytest.fixture
def pg_engine():
    engine = get_pg_engine()
    if engine is None:
        pytest.skip("PostgreSQL is unavailable at configured DATABASE_URL.")
    return engine


def test_expired_checkout_caller_transaction_settles_correctly(pg_engine):
    """Caller-managed transaction: checkout raises ReservationExpiredError, rolling back checkout.

    The application handles the expected failure by settling the expired reservation
    in a dedicated transaction. A fresh database session confirms the reservation is
    CANCELLED and the item is AVAILABLE.
    """
    session_factory = sessionmaker(bind=pg_engine)
    setup_session = session_factory()

    now = datetime.now(UTC)
    member = Member(
        name="Tx Member 1",
        phone="+91-77777-00001",
        join_date=now,
        status=MemberStatus.ACTIVE,
    )
    item = Item(
        name="Tx Drill 1",
        category="Drills",
        replacement_value=25000,
        status=ItemStatus.RESERVED,
    )
    setup_session.add_all([member, item])
    setup_session.flush()

    # 1. Create a reservation that has expired (50h ago)
    loan = Loan(
        member_id=member.id,
        item_id=item.id,
        status=LoanStatus.RESERVED,
        reserved_at=now - timedelta(hours=50),
        fee_charged=0,
    )
    setup_session.add(loan)
    setup_session.commit()
    loan_id = loan.id
    item_id = item.id
    member_id = member.id
    setup_session.close()

    # 2. Attempt checkout inside caller-managed transaction
    app_session = session_factory()
    checkout_failed = False
    try:
        with app_session.begin():
            LoanService.checkout(app_session, loan_id=loan_id, now=now)
    except ReservationExpiredError:
        checkout_failed = True
        # 3. Handle expected failure as application would: settle in dedicated transaction
        with app_session.begin():
            LoanService.settle_expired_reservation(app_session, loan_id=loan_id, now=now)
    finally:
        app_session.close()

    assert checkout_failed is True

    # 4. Verify from fresh database session that states are correct
    verify_session = session_factory()
    try:
        fresh_loan = verify_session.get(Loan, loan_id)
        assert fresh_loan.status == LoanStatus.CANCELLED
        assert fresh_loan.cancelled_at is not None
        fresh_item = verify_session.get(Item, item_id)
        assert fresh_item.status == ItemStatus.AVAILABLE
    finally:
        verify_session.delete(fresh_loan)
        verify_session.delete(fresh_item)
        verify_session.delete(verify_session.get(Member, member_id))
        verify_session.commit()
        verify_session.close()


def test_expired_checkout_outcome_pattern_commits_expiry_in_single_transaction(pg_engine):
    """Outcome pattern allows caller to safely commit expiry cleanup in a single transaction."""
    session_factory = sessionmaker(bind=pg_engine)
    setup_session = session_factory()

    now = datetime.now(UTC)
    member = Member(
        name="Tx Member 2",
        phone="+91-77777-00002",
        join_date=now,
        status=MemberStatus.ACTIVE,
    )
    item = Item(
        name="Tx Saw 2",
        category="Saws",
        replacement_value=35000,
        status=ItemStatus.RESERVED,
    )
    setup_session.add_all([member, item])
    setup_session.flush()

    loan = Loan(
        member_id=member.id,
        item_id=item.id,
        status=LoanStatus.RESERVED,
        reserved_at=now - timedelta(hours=50),
        fee_charged=0,
    )
    setup_session.add(loan)
    setup_session.commit()
    loan_id = loan.id
    item_id = item.id
    member_id = member.id
    setup_session.close()

    # Attempt checkout using outcome pattern inside a single caller transaction
    app_session = session_factory()
    try:
        with app_session.begin():
            outcome = LoanService.checkout_with_outcome(app_session, loan_id=loan_id, now=now)
            assert outcome.success is False
            assert outcome.is_expired is True
            assert "expired" in outcome.rejection_reason.lower()
    finally:
        app_session.close()

    # Fresh session confirms transaction committed the cancellation and item availability
    verify_session = session_factory()
    try:
        fresh_loan = verify_session.get(Loan, loan_id)
        assert fresh_loan.status == LoanStatus.CANCELLED
        assert fresh_loan.cancelled_at is not None
        fresh_item = verify_session.get(Item, item_id)
        assert fresh_item.status == ItemStatus.AVAILABLE
    finally:
        verify_session.delete(fresh_loan)
        verify_session.delete(fresh_item)
        verify_session.delete(verify_session.get(Member, member_id))
        verify_session.commit()
        verify_session.close()


def test_checkout_failure_due_to_ineligibility_rolls_back_cleanly(pg_engine):
    """When checkout fails due to member suspension, all mutations roll back atomically."""
    session_factory = sessionmaker(bind=pg_engine)
    setup_session = session_factory()

    now = datetime.now(UTC)
    member = Member(
        name="Suspended Borrower",
        phone="+91-77777-00003",
        join_date=now,
        status=MemberStatus.SUSPENDED,  # Suspended
    )
    item = Item(
        name="Tx Router",
        category="Routers",
        replacement_value=20000,
        status=ItemStatus.RESERVED,
    )
    setup_session.add_all([member, item])
    setup_session.flush()

    loan = Loan(
        member_id=member.id,
        item_id=item.id,
        status=LoanStatus.RESERVED,
        reserved_at=now - timedelta(hours=10),
        fee_charged=0,
    )
    setup_session.add(loan)
    setup_session.commit()
    loan_id = loan.id
    item_id = item.id
    member_id = member.id
    setup_session.close()

    app_session = session_factory()
    with pytest.raises(MemberSuspendedError), app_session.begin():
        LoanService.checkout(app_session, loan_id=loan_id, now=now)
    app_session.close()

    # Fresh session confirms transaction rolled back completely
    verify_session = session_factory()
    try:
        fresh_loan = verify_session.get(Loan, loan_id)
        assert fresh_loan.status == LoanStatus.RESERVED
        assert fresh_loan.checked_out_at is None
        fresh_item = verify_session.get(Item, item_id)
        assert fresh_item.status == ItemStatus.RESERVED
    finally:
        verify_session.delete(fresh_loan)
        verify_session.delete(fresh_item)
        verify_session.delete(verify_session.get(Member, member_id))
        verify_session.commit()
        verify_session.close()


def test_overpayment_failure_rolls_back_balance_and_payment_rows(pg_engine):
    """When payment fails validation (overpayment), balance is untouched and no payment recorded."""
    session_factory = sessionmaker(bind=pg_engine)
    setup_session = session_factory()

    now = datetime.now(UTC)
    member = Member(
        name="Tx Pay Member",
        phone="+91-77777-00004",
        join_date=now,
        status=MemberStatus.ACTIVE,
        running_fee_balance=2000,  # ₹20
    )
    setup_session.add(member)
    setup_session.commit()
    member_id = member.id
    setup_session.close()

    app_session = session_factory()
    with pytest.raises(OverpaymentError), app_session.begin():
        MemberService.record_payment(
            app_session,
            member_id=member_id,
            amount=5000,
            now=now,  # ₹50 > ₹20
        )
    app_session.close()

    verify_session = session_factory()
    try:
        fresh_member = verify_session.get(Member, member_id)
        assert fresh_member.running_fee_balance == 2000  # Untouched
        payments = verify_session.query(Payment).filter(Payment.member_id == member_id).all()
        assert len(payments) == 0  # Zero payment rows
    finally:
        verify_session.delete(verify_session.get(Member, member_id))
        verify_session.commit()
        verify_session.close()

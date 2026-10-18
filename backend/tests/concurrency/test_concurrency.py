"""Concurrency integration tests verifying pessimistic row locking against PostgreSQL.

Tests that concurrent checkout and reservation attempts on the same record cannot
produce double-checkout or duplicate reservations.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.domain.exceptions import (
    InvalidLoanStateError,
    ItemNotAvailableError,
    OverpaymentError,
)
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
        engine = create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5)
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


def test_concurrent_checkout_prevents_double_checkout(pg_engine):
    """Two concurrent checkout requests on the same reservation: exactly one succeeds.

    The second request is blocked by with_for_update() and then rejects checkout
    because status transitioned to CHECKED_OUT.
    """
    session_factory = sessionmaker(bind=pg_engine)
    setup_session = session_factory()

    now = datetime.now(UTC)
    member = Member(
        name="Concurrent Member 1",
        phone="+91-88888-00001",
        join_date=now,
        status=MemberStatus.ACTIVE,
    )
    item = Item(
        name="Concurrent Drill 1",
        category="Drills",
        replacement_value=40000,
        status=ItemStatus.RESERVED,
    )
    setup_session.add_all([member, item])
    setup_session.flush()

    loan = Loan(
        member_id=member.id,
        item_id=item.id,
        status=LoanStatus.RESERVED,
        reserved_at=now,
        fee_charged=0,
    )
    setup_session.add(loan)
    setup_session.commit()
    loan_id = loan.id
    member_id = member.id
    item_id = item.id
    setup_session.close()

    results: list[str] = []
    errors: list[Exception] = []

    def attempt_checkout(worker_id: int):
        s = session_factory()
        try:
            with s.begin():
                LoanService.checkout(s, loan_id=loan_id, now=now + timedelta(minutes=5))
            results.append(f"worker_{worker_id}_success")
        except Exception as e:
            errors.append(e)
            results.append(f"worker_{worker_id}_error")
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(attempt_checkout, 1)
        f2 = executor.submit(attempt_checkout, 2)
        f1.result()
        f2.result()

    # Verification: exactly one succeeded and one raised InvalidLoanStateError
    assert results.count("worker_1_success") + results.count("worker_2_success") == 1
    assert len(errors) == 1
    assert isinstance(errors[0], InvalidLoanStateError)

    # Verify final DB state
    verify_session = session_factory()
    try:
        final_loan = verify_session.get(Loan, loan_id)
        assert final_loan.status == LoanStatus.CHECKED_OUT
        final_item = verify_session.get(Item, item_id)
        assert final_item.status == ItemStatus.CHECKED_OUT
    finally:
        # Cleanup
        to_del_loan = verify_session.get(Loan, loan_id)
        if to_del_loan:
            verify_session.delete(to_del_loan)
        to_del_item = verify_session.get(Item, item_id)
        if to_del_item:
            verify_session.delete(to_del_item)
        to_del_member = verify_session.get(Member, member_id)
        if to_del_member:
            verify_session.delete(to_del_member)
        verify_session.commit()
        verify_session.close()


def test_concurrent_reserve_same_item_prevents_double_reservation(pg_engine):
    """Two concurrent reservations on the same available item: exactly one succeeds."""
    session_factory = sessionmaker(bind=pg_engine)
    setup_session = session_factory()

    now = datetime.now(UTC)
    m1 = Member(name="Res Member 1", phone="+91-88888-00002", join_date=now)
    m2 = Member(name="Res Member 2", phone="+91-88888-00003", join_date=now)
    item = Item(
        name="Concurrent Saw 1",
        category="Saws",
        replacement_value=35000,
        status=ItemStatus.AVAILABLE,
    )
    setup_session.add_all([m1, m2, item])
    setup_session.commit()
    m1_id, m2_id, item_id = m1.id, m2.id, item.id
    setup_session.close()

    results: list[str] = []
    errors: list[Exception] = []
    created_loans: list[int] = []

    def attempt_reserve(member_id: int, worker_id: int):
        s = session_factory()
        try:
            with s.begin():
                loan = LoanService.reserve(s, member_id=member_id, item_id=item_id, now=now)
                created_loans.append(loan.id)
            results.append(f"worker_{worker_id}_success")
        except Exception as e:
            errors.append(e)
            results.append(f"worker_{worker_id}_error")
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(attempt_reserve, m1_id, 1)
        f2 = executor.submit(attempt_reserve, m2_id, 2)
        f1.result()
        f2.result()

    # Verification: exactly one succeeded and one raised ItemNotAvailableError
    assert results.count("worker_1_success") + results.count("worker_2_success") == 1
    assert len(errors) == 1
    assert isinstance(errors[0], ItemNotAvailableError)

    # Verify final DB state
    verify_session = session_factory()
    try:
        active_loans = (
            verify_session.query(Loan)
            .filter(Loan.item_id == item_id, Loan.status == LoanStatus.RESERVED)
            .all()
        )
        assert len(active_loans) == 1
        final_item = verify_session.get(Item, item_id)
        assert final_item.status == ItemStatus.RESERVED
    finally:
        # Cleanup
        for loan_id in created_loans:
            l_obj = verify_session.get(Loan, loan_id)
            if l_obj:
                verify_session.delete(l_obj)
        verify_session.delete(verify_session.get(Item, item_id))
        verify_session.delete(verify_session.get(Member, m1_id))
        verify_session.delete(verify_session.get(Member, m2_id))
        verify_session.commit()
        verify_session.close()


def test_concurrent_return_prevents_double_return_and_fee(pg_engine):
    """Two concurrent return requests on the same checked-out loan: exactly one succeeds.

    The second request is blocked by with_for_update() and then rejects return
    because status transitioned to RETURNED. Member balance is only charged once.
    """
    session_factory = sessionmaker(bind=pg_engine)
    setup_session = session_factory()

    now = datetime.now(UTC)
    member = Member(
        name="Concurrent Member Ret",
        phone="+91-88888-00004",
        join_date=now - timedelta(days=20),
        status=MemberStatus.ACTIVE,
        running_fee_balance=0,
    )
    item = Item(
        name="Concurrent Sander 1",
        category="Sanders",
        replacement_value=30000,
        status=ItemStatus.CHECKED_OUT,
    )
    setup_session.add_all([member, item])
    setup_session.flush()

    loan = Loan(
        member_id=member.id,
        item_id=item.id,
        status=LoanStatus.CHECKED_OUT,
        reserved_at=now - timedelta(days=10),
        checked_out_at=now - timedelta(days=10),
        due_at=now - timedelta(days=3),  # 3 days late -> ₹30 (3000 paise)
        fee_charged=0,
    )
    setup_session.add(loan)
    setup_session.commit()
    loan_id = loan.id
    member_id = member.id
    item_id = item.id
    setup_session.close()

    results: list[str] = []
    errors: list[Exception] = []

    def attempt_return(worker_id: int):
        s = session_factory()
        try:
            with s.begin():
                LoanService.return_item(s, loan_id=loan_id, now=now)
            results.append(f"worker_{worker_id}_success")
        except Exception as e:
            errors.append(e)
            results.append(f"worker_{worker_id}_error")
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(attempt_return, 1)
        f2 = executor.submit(attempt_return, 2)
        f1.result()
        f2.result()

    assert results.count("worker_1_success") + results.count("worker_2_success") == 1
    assert len(errors) == 1
    assert isinstance(errors[0], InvalidLoanStateError)

    verify_session = session_factory()
    try:
        final_loan = verify_session.get(Loan, loan_id)
        assert final_loan.status == LoanStatus.RETURNED
        assert final_loan.fee_charged == 3000
        final_member = verify_session.get(Member, member_id)
        assert final_member.running_fee_balance == 3000  # Charged once, not twice!
        final_item = verify_session.get(Item, item_id)
        assert final_item.status == ItemStatus.AVAILABLE
    finally:
        to_del_loan = verify_session.get(Loan, loan_id)
        if to_del_loan:
            verify_session.delete(to_del_loan)
        to_del_item = verify_session.get(Item, item_id)
        if to_del_item:
            verify_session.delete(to_del_item)
        to_del_member = verify_session.get(Member, member_id)
        if to_del_member:
            verify_session.delete(to_del_member)
        verify_session.commit()
        verify_session.close()


def test_concurrent_payment_prevents_negative_balance(pg_engine):
    """Two concurrent payments competing for balance: member lock serializes deductions.

    Overpayment beyond outstanding balance is rejected, preventing balance from going negative.
    """
    session_factory = sessionmaker(bind=pg_engine)
    setup_session = session_factory()

    now = datetime.now(UTC)
    member = Member(
        name="Concurrent Member Pay",
        phone="+91-88888-00005",
        join_date=now - timedelta(days=30),
        status=MemberStatus.ACTIVE,
        running_fee_balance=5000,  # ₹50 outstanding balance
    )
    setup_session.add(member)
    setup_session.commit()
    member_id = member.id
    setup_session.close()

    results: list[str] = []
    errors: list[Exception] = []

    def attempt_payment(worker_id: int):
        s = session_factory()
        try:
            with s.begin():
                # Each thread tries to pay ₹30 (3000 paise). Total ₹60 > ₹50 balance.
                MemberService.record_payment(
                    s, member_id=member_id, amount=3000, note=f"Worker {worker_id}", now=now
                )
            results.append(f"worker_{worker_id}_success")
        except Exception as e:
            errors.append(e)
            results.append(f"worker_{worker_id}_error")
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(attempt_payment, 1)
        f2 = executor.submit(attempt_payment, 2)
        f1.result()
        f2.result()

    # Exactly one payment of ₹30 succeeds; the other is rejected as OverpaymentError
    assert results.count("worker_1_success") + results.count("worker_2_success") == 1
    assert len(errors) == 1
    assert isinstance(errors[0], OverpaymentError)

    verify_session = session_factory()
    try:
        final_member = verify_session.get(Member, member_id)
        assert final_member.running_fee_balance == 2000  # ₹50 - ₹30 = ₹20 (never negative)
        payments = verify_session.query(Payment).filter(Payment.member_id == member_id).all()
        assert len(payments) == 1
        assert payments[0].amount == 3000
    finally:
        for p in verify_session.query(Payment).filter(Payment.member_id == member_id).all():
            verify_session.delete(p)
        to_del_member = verify_session.get(Member, member_id)
        if to_del_member:
            verify_session.delete(to_del_member)
        verify_session.commit()
        verify_session.close()

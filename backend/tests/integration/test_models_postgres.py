"""Integration tests verifying database check constraints and foreign keys against PostgreSQL."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.models.item import Item, ItemStatus
from app.models.loan import Loan, LoanStatus
from app.models.member import Member, MemberStatus
from app.models.payment import Payment

pytestmark = pytest.mark.integration


def get_pg_session() -> Session | None:
    """Connect to PostgreSQL using the configured DATABASE_URL."""
    url = Settings.from_env().database_url
    if not url or "postgresql" not in url:
        return None
    try:
        engine = create_engine(url, pool_pre_ping=True)
        with engine.connect():
            pass
        return sessionmaker(bind=engine)()
    except Exception:
        return None


@pytest.fixture
def db_session():
    session = get_pg_session()
    if session is None:
        pytest.skip("PostgreSQL is unavailable at configured DATABASE_URL.")
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_member_negative_balance_rejected(db_session: Session):
    """PostgreSQL constraint ck_members_balance_non_negative must reject negative fee balance."""
    member = Member(
        name="Invalid Member",
        phone="+91-00000-00099",
        join_date=datetime.now(UTC),
        status=MemberStatus.ACTIVE,
        running_fee_balance=-500,  # Negative balance
    )
    db_session.add(member)
    with pytest.raises(IntegrityError) as exc_info:
        db_session.flush()
    assert "ck_members_balance_non_negative" in str(exc_info.value)


def test_item_non_positive_replacement_value_rejected(db_session: Session):
    """PostgreSQL constraint ck_items_replacement_value_positive rejects replacement_value <= 0."""
    item = Item(
        name="Zero Value Drill",
        category="Drills",
        replacement_value=0,
        status=ItemStatus.AVAILABLE,
    )
    db_session.add(item)
    with pytest.raises(IntegrityError) as exc_info:
        db_session.flush()
    assert "ck_items_replacement_value_positive" in str(exc_info.value)


def test_payment_non_positive_amount_rejected(db_session: Session):
    """PostgreSQL constraint ck_payments_amount_positive must reject payment amount <= 0."""
    now = datetime.now(UTC)
    member = Member(
        name="Payment Test Member",
        phone="+91-00000-00098",
        join_date=now,
        status=MemberStatus.ACTIVE,
        running_fee_balance=1000,
    )
    db_session.add(member)
    db_session.flush()

    payment = Payment(
        member_id=member.id,
        amount=0,
        paid_at=now,
    )
    db_session.add(payment)
    with pytest.raises(IntegrityError) as exc_info:
        db_session.flush()
    assert "ck_payments_amount_positive" in str(exc_info.value)


def test_loan_reserved_state_requires_null_checkout_and_return(db_session: Session):
    """A RESERVED loan cannot have checked_out_at or returned_at set."""
    now = datetime.now(UTC)
    member = Member(name="Loan Test M1", phone="+91-00000-00097", join_date=now)
    item = Item(name="Loan Test Item 1", category="Drills", replacement_value=50000)
    db_session.add_all([member, item])
    db_session.flush()

    # Invalid: status is RESERVED but checked_out_at is set
    loan = Loan(
        member_id=member.id,
        item_id=item.id,
        status=LoanStatus.RESERVED,
        reserved_at=now,
        checked_out_at=now,  # Contradicts RESERVED status
    )
    db_session.add(loan)
    with pytest.raises(IntegrityError) as exc_info:
        db_session.flush()
    assert "ck_loans_reserved_timestamps" in str(exc_info.value)


def test_loan_checked_out_requires_due_at_greater_than_checkout(db_session: Session):
    """A CHECKED_OUT loan must have due_at > checked_out_at."""
    now = datetime.now(UTC)
    member = Member(name="Loan Test M2", phone="+91-00000-00096", join_date=now)
    item = Item(name="Loan Test Item 2", category="Drills", replacement_value=50000)
    db_session.add_all([member, item])
    db_session.flush()

    # Invalid: due_at is before checked_out_at
    loan = Loan(
        member_id=member.id,
        item_id=item.id,
        status=LoanStatus.CHECKED_OUT,
        reserved_at=now - timedelta(hours=1),
        checked_out_at=now,
        due_at=now - timedelta(days=1),  # Invalid due_at <= checked_out_at
    )
    db_session.add(loan)
    with pytest.raises(IntegrityError) as exc_info:
        db_session.flush()
    assert "ck_loans_checked_out_timestamps" in str(exc_info.value)


def test_loan_returned_requires_returned_at(db_session: Session):
    """A RETURNED loan must have returned_at set."""
    now = datetime.now(UTC)
    member = Member(name="Loan Test M3", phone="+91-00000-00095", join_date=now)
    item = Item(name="Loan Test Item 3", category="Drills", replacement_value=50000)
    db_session.add_all([member, item])
    db_session.flush()

    # Invalid: status is RETURNED but returned_at is None
    loan = Loan(
        member_id=member.id,
        item_id=item.id,
        status=LoanStatus.RETURNED,
        reserved_at=now - timedelta(days=5),
        checked_out_at=now - timedelta(days=5),
        due_at=now + timedelta(days=2),
        returned_at=None,  # Invalid
    )
    db_session.add(loan)
    with pytest.raises(IntegrityError) as exc_info:
        db_session.flush()
    assert "ck_loans_returned_timestamps" in str(exc_info.value)


def test_loan_cancelled_requires_cancelled_at(db_session: Session):
    """A CANCELLED loan must have cancelled_at set."""
    now = datetime.now(UTC)
    member = Member(name="Loan Test M4", phone="+91-00000-00094", join_date=now)
    item = Item(name="Loan Test Item 4", category="Drills", replacement_value=50000)
    db_session.add_all([member, item])
    db_session.flush()

    # Invalid: status is CANCELLED but cancelled_at is None
    loan = Loan(
        member_id=member.id,
        item_id=item.id,
        status=LoanStatus.CANCELLED,
        reserved_at=now - timedelta(hours=2),
        cancelled_at=None,  # Invalid
    )
    db_session.add(loan)
    with pytest.raises(IntegrityError) as exc_info:
        db_session.flush()
    assert "ck_loans_cancelled_timestamps" in str(exc_info.value)


def test_foreign_key_delete_restrict_prevents_orphan_history(db_session: Session):
    """Attempting to delete a member who has associated loans must raise IntegrityError."""
    now = datetime.now(UTC)
    member = Member(name="History Member", phone="+91-00000-00093", join_date=now)
    item = Item(name="History Item", category="Drills", replacement_value=50000)
    db_session.add_all([member, item])
    db_session.flush()

    loan = Loan(
        member_id=member.id,
        item_id=item.id,
        status=LoanStatus.RESERVED,
        reserved_at=now,
    )
    db_session.add(loan)
    db_session.flush()

    db_session.delete(member)
    with pytest.raises(IntegrityError):
        db_session.flush()

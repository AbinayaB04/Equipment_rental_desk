"""Business-rule behavioral specification test contracts for Milestone 2 (M2).

These tests specify the exact business requirements from Problem 1: Equipment Rental Desk.
In accordance with Milestone 1 requirements, these tests define the behavior contracts
prior to M2 service-layer implementation.

To run these M2 specifications explicitly:
    pytest tests/unit/test_business_rules_spec.py -m m2_spec

Expected M1 status: FAILING / UNIMPLEMENTED until M2 implements the service layer.
"""

from datetime import UTC, datetime, timedelta

import pytest

# Marker to cleanly separate M2 specification contracts from default M0/M1 test run
pytestmark = pytest.mark.m2_spec


def test_rule_1_item_state_machine_valid_transitions():
    """Rule 1: Available -> Reserved -> Checked Out -> Available."""
    from app.services.loan_service import LoanService  # noqa: F401 - Planned for M2

    raise NotImplementedError("LoanService.reserve/checkout/return planned for M2")


def test_rule_1_overdue_is_dynamically_computed_not_cron():
    """Rule 1: From Checked Out, an item becomes Overdue automatically once due_at passes."""
    from app.services.loan_service import LoanService  # noqa: F401 - Planned for M2

    raise NotImplementedError("Dynamic overdue calculation planned for M2")


def test_rule_2_reservation_active_at_47h_59m():
    """Rule 2: A reservation holds an item for 48 hours; valid at 47 hours 59 minutes."""
    from app.services.loan_service import LoanService  # noqa: F401 - Planned for M2

    raise NotImplementedError("Reservation 48h active boundary planned for M2")


def test_rule_2_reservation_expires_at_exact_48_hours():
    """Rule 2: A reservation expires at exactly 48 hours; item is effectively Available again."""
    from app.services.loan_service import LoanService  # noqa: F401 - Planned for M2

    raise NotImplementedError("Reservation 48h expiry boundary planned for M2")


def test_rule_3_loan_period_is_7_days_from_checkout():
    """Rule 3: Loan period is exactly 7 days from checkout."""
    from app.services.loan_service import LoanService  # noqa: F401 - Planned for M2

    raise NotImplementedError("7-day loan duration planned for M2")


def test_rule_3_late_fee_at_due_date_boundary():
    """Rule 3: 0 fee at or before due_at; ₹10 at 1 second past due_at."""
    from app.services.fee_service import calculate_late_fee  # noqa: F401 - Planned for M2

    now = datetime.now(UTC)
    due_at = now
    # 0 seconds overdue -> 0 fee
    assert calculate_late_fee(return_time=now, due_at=due_at, replacement_value=50000) == 0
    # 1 second overdue -> 1st day (1000 paise = ₹10)
    assert (
        calculate_late_fee(
            return_time=now + timedelta(seconds=1), due_at=due_at, replacement_value=50000
        )
        == 1000
    )


def test_rule_3_late_fee_24h_increments():
    """Rule 3: 24h 0s late is ₹10; 24h 1s late is ₹20."""
    from app.services.fee_service import calculate_late_fee  # noqa: F401 - Planned for M2

    now = datetime.now(UTC)
    due_at = now
    assert (
        calculate_late_fee(
            return_time=now + timedelta(hours=24), due_at=due_at, replacement_value=50000
        )
        == 1000
    )
    assert (
        calculate_late_fee(
            return_time=now + timedelta(hours=24, seconds=1), due_at=due_at, replacement_value=50000
        )
        == 2000
    )


def test_rule_3_late_fee_capped_at_200_rupees():
    """Rule 3: Late fee capped at ₹200 (20,000 paise) per loan."""
    from app.services.fee_service import calculate_late_fee  # noqa: F401 - Planned for M2

    now = datetime.now(UTC)
    due_at = now
    # 25 days overdue on a ₹1,000 item -> capped at ₹200
    fee = calculate_late_fee(
        return_time=now + timedelta(days=25), due_at=due_at, replacement_value=100000
    )
    assert fee == 20000


def test_rule_3_late_fee_capped_at_replacement_value():
    """Rule 3: Late fee never exceeds the item's replacement value."""
    from app.services.fee_service import calculate_late_fee  # noqa: F401 - Planned for M2

    now = datetime.now(UTC)
    due_at = now
    # 25 days overdue on a ₹150 item (15,000 paise) -> capped at ₹150, not ₹200
    fee = calculate_late_fee(
        return_time=now + timedelta(days=25), due_at=due_at, replacement_value=15000
    )
    assert fee == 15000


def test_rule_4_member_at_most_3_active_loans():
    """Rule 4: A member may hold at most 3 active loans (Reserved, Checked Out, Overdue)."""
    from app.services.member_service import MemberService  # noqa: F401 - Planned for M2

    raise NotImplementedError("3-loan active limit planned for M2")


def test_rule_5_member_balance_boundary():
    """Rule 5: Balance <= ₹100 is eligible; balance > ₹100 is blocked."""
    from app.services.member_service import MemberService  # noqa: F401 - Planned for M2

    raise NotImplementedError("Member ₹100 balance eligibility planned for M2")


def test_rule_5_overdue_14_days_boundary():
    """Rule 5: Any loan overdue > 14 days blocks borrowing; exactly 14 days is eligible."""
    from app.services.member_service import MemberService  # noqa: F401 - Planned for M2

    raise NotImplementedError("14-day overdue borrowing block planned for M2")


def test_rule_6_return_of_item_not_checked_out_rejected():
    """Rule 6: A return of an item that is not checked out is an error, not a no-op."""
    from app.services.loan_service import LoanService  # noqa: F401 - Planned for M2

    raise NotImplementedError("Return error handling planned for M2")


def test_rule_7_suspended_member_cannot_transact():
    """Rule 7: Suspended members cannot reserve, check out, or transact."""
    from app.services.member_service import MemberService  # noqa: F401 - Planned for M2

    raise NotImplementedError("Suspension enforcement planned for M2")


def test_maintenance_cancels_pending_reservation():
    """Maintenance: Placing a RESERVED item into maintenance cancels the reservation."""
    from app.services.item_service import ItemService  # noqa: F401 - Planned for M2

    raise NotImplementedError("Maintenance cancellation of reservation planned for M2")


def test_maintenance_on_checked_out_item_permits_return():
    """Maintenance: Marking a CHECKED_OUT item for maintenance leaves loan open and returnable."""
    from app.services.item_service import ItemService  # noqa: F401 - Planned for M2

    raise NotImplementedError("Maintenance on checked-out item planned for M2")

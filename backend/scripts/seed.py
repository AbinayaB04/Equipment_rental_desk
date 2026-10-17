"""Idempotent seed data script for Equipment Rental Desk.

Populates realistic sample data representing tool-library inventory, members in
various eligibility states, active/overdue loans, and historical payment/fee records.
"""

from datetime import UTC, datetime, timedelta

from app.core.database import session_scope
from app.models.item import Item, ItemStatus
from app.models.loan import Loan, LoanStatus
from app.models.member import Member, MemberStatus
from app.models.payment import Payment

# Deterministic namespace prefix and identifiers for safe idempotency
SEED_PHONE_PREFIX = "+91-98000-000"
EXPECTED_SEED_PHONES = tuple(f"{SEED_PHONE_PREFIX}{i:02d}" for i in range(1, 9))
EXPECTED_ITEM_TAGS = tuple(f"[SEED-{i:02d}]" for i in range(1, 11))

# Expected loans defined by (member_phone, item_seed_tag)
EXPECTED_SEED_LOANS = (
    (f"{SEED_PHONE_PREFIX}02", "[SEED-02]"),
    (f"{SEED_PHONE_PREFIX}01", "[SEED-03]"),
    (f"{SEED_PHONE_PREFIX}03", "[SEED-04]"),
    (f"{SEED_PHONE_PREFIX}03", "[SEED-05]"),
    (f"{SEED_PHONE_PREFIX}03", "[SEED-06]"),
    (f"{SEED_PHONE_PREFIX}07", "[SEED-07]"),
    (f"{SEED_PHONE_PREFIX}04", "[SEED-09]"),
    (f"{SEED_PHONE_PREFIX}05", "[SEED-10]"),
    (f"{SEED_PHONE_PREFIX}06", "[SEED-10]"),
)

# Expected payments defined by (member_phone, amount_in_paise)
EXPECTED_SEED_PAYMENTS = ((f"{SEED_PHONE_PREFIX}04", 5000),)


def seed_database(database_url: str | None = None) -> bool:
    """Populate the database with realistic seed data if not already present.

    Verifies the entire seed dataset (members, items, loans, and payments) and
    checks the balance invariant. If any records are missing or inconsistent,
    prints a clear warning and skips all insertion/modification without
    deleting or overwriting existing data.

    Returns True if data was inserted, False if already present or incomplete/inconsistent.
    """
    with session_scope(database_url) as session:
        # 1. Query any existing records using stable seed identifiers
        existing_members = (
            session.query(Member).filter(Member.phone.in_(EXPECTED_SEED_PHONES)).all()
        )
        existing_items = session.query(Item).filter(Item.name.contains("[SEED-")).all()
        existing_loans = (
            session.query(Loan)
            .join(Member, Loan.member_id == Member.id)
            .filter(Member.phone.in_(EXPECTED_SEED_PHONES))
            .all()
        )
        existing_payments = (
            session.query(Payment)
            .join(Member, Payment.member_id == Member.id)
            .filter(Member.phone.in_(EXPECTED_SEED_PHONES))
            .all()
        )

        has_any_seed_data = bool(
            existing_members or existing_items or existing_loans or existing_payments
        )

        if has_any_seed_data:
            issues: list[str] = []

            # Check members completeness
            existing_phone_set = {m.phone for m in existing_members}
            missing_phones = [p for p in EXPECTED_SEED_PHONES if p not in existing_phone_set]
            if missing_phones:
                issues.append(
                    f"Missing seed member(s): {', '.join(missing_phones)} "
                    f"(found {len(existing_members)}/{len(EXPECTED_SEED_PHONES)})"
                )

            # Check items completeness
            item_by_id = {item.id: item for item in existing_items}
            found_tags = {
                tag
                for tag in EXPECTED_ITEM_TAGS
                if any(tag in item.name for item in existing_items)
            }
            missing_tags = [tag for tag in EXPECTED_ITEM_TAGS if tag not in found_tags]
            if missing_tags:
                issues.append(
                    f"Missing seed item(s): {', '.join(missing_tags)} "
                    f"(found {len(existing_items)}/{len(EXPECTED_ITEM_TAGS)})"
                )

            # Check loans completeness
            member_by_id = {m.id: m for m in existing_members}
            existing_loan_pairs: set[tuple[str, str]] = set()
            for loan in existing_loans:
                member = member_by_id.get(loan.member_id)
                item = item_by_id.get(loan.item_id)
                if member and item:
                    for tag in EXPECTED_ITEM_TAGS:
                        if tag in item.name:
                            existing_loan_pairs.add((member.phone, tag))
                            break

            missing_loans = [
                pair for pair in EXPECTED_SEED_LOANS if pair not in existing_loan_pairs
            ]
            if missing_loans:
                loan_desc = ", ".join(f"({p}, {t})" for p, t in missing_loans)
                issues.append(
                    f"Missing seed loan(s): {loan_desc} "
                    f"(found {len(existing_loans)}/{len(EXPECTED_SEED_LOANS)})"
                )

            # Check payments completeness
            existing_payment_specs: set[tuple[str, int]] = set()
            for payment in existing_payments:
                member = member_by_id.get(payment.member_id)
                if member:
                    existing_payment_specs.add((member.phone, payment.amount))

            missing_payments = [
                spec for spec in EXPECTED_SEED_PAYMENTS if spec not in existing_payment_specs
            ]
            if missing_payments:
                pay_desc = ", ".join(f"({p}, ₹{amt / 100:.0f})" for p, amt in missing_payments)
                issues.append(
                    f"Missing seed payment(s): {pay_desc} "
                    f"(found {len(existing_payments)}/{len(EXPECTED_SEED_PAYMENTS)})"
                )

            # Verify balance invariant for all existing seed members
            balance_inconsistencies: list[str] = []
            for member in existing_members:
                member_loans = [loan for loan in existing_loans if loan.member_id == member.id]
                member_payments = [
                    payment for payment in existing_payments if payment.member_id == member.id
                ]
                total_fees = sum(loan.fee_charged for loan in member_loans)
                total_payments = sum(payment.amount for payment in member_payments)
                expected_balance = total_fees - total_payments
                if member.running_fee_balance != expected_balance:
                    balance_inconsistencies.append(
                        f"Member '{member.name}' ({member.phone}): "
                        f"balance={member.running_fee_balance}, expected={expected_balance} "
                        f"(fees={total_fees}, payments={total_payments})"
                    )

            if balance_inconsistencies:
                issues.append("Balance inconsistency(ies):")
                for bi in balance_inconsistencies:
                    issues.append(f"  - {bi}")

            if issues:
                print("WARNING: Incomplete or inconsistent seed dataset detected:")
                for issue in issues:
                    print(f"  - {issue}")
                print("Skipping all insertion or modification to preserve existing data.")
                return False

            print(
                "Seed dataset already exists and is fully verified (8 members, 10 items, "
                "9 loans, 1 payment; all balances consistent). "
                "Skipping insertion to avoid duplicates."
            )
            return False

        now = datetime.now(UTC)

        # 2. Members
        # Invariant: running_fee_balance == sum(fees_charged on returned loans) - sum(payments)
        members = [
            # Member 0: Clean active member (eligible, 0 loans, 0 balance)
            Member(
                name="Aarav Sharma",
                phone=f"{SEED_PHONE_PREFIX}01",
                join_date=now - timedelta(days=90),
                status=MemberStatus.ACTIVE,
                running_fee_balance=0,
            ),
            # Member 1: Active with 1 active loan
            Member(
                name="Priya Patel",
                phone=f"{SEED_PHONE_PREFIX}02",
                join_date=now - timedelta(days=60),
                status=MemberStatus.ACTIVE,
                running_fee_balance=0,
            ),
            # Member 2: Active with 3 active loans (at 3-loan limit)
            Member(
                name="Vikram Singh",
                phone=f"{SEED_PHONE_PREFIX}03",
                join_date=now - timedelta(days=120),
                status=MemberStatus.ACTIVE,
                running_fee_balance=0,
            ),
            # Member 3: Active with ₹50 fee balance (under ₹100, eligible)
            # Invariant: 10,000 fee - 5,000 payment = 5,000 paise (₹50)
            Member(
                name="Ananya Rao",
                phone=f"{SEED_PHONE_PREFIX}04",
                join_date=now - timedelta(days=45),
                status=MemberStatus.ACTIVE,
                running_fee_balance=5000,
            ),
            # Member 4: Active with exactly ₹100 fee balance (exact boundary test, eligible)
            # Invariant: 10,000 fee - 0 payment = 10,000 paise (₹100)
            Member(
                name="Kavita Nair",
                phone=f"{SEED_PHONE_PREFIX}05",
                join_date=now - timedelta(days=30),
                status=MemberStatus.ACTIVE,
                running_fee_balance=10000,
            ),
            # Member 5: Blocked with ₹120 fee balance (> ₹100, cannot borrow)
            # Invariant: 12,000 fee - 0 payment = 12,000 paise (₹120)
            Member(
                name="Rohan Mehta",
                phone=f"{SEED_PHONE_PREFIX}06",
                join_date=now - timedelta(days=15),
                status=MemberStatus.ACTIVE,
                running_fee_balance=12000,
            ),
            # Member 6: Blocked with a loan overdue > 14 days (cannot borrow)
            Member(
                name="Devendra Joshi",
                phone=f"{SEED_PHONE_PREFIX}07",
                join_date=now - timedelta(days=40),
                status=MemberStatus.ACTIVE,
                running_fee_balance=0,
            ),
            # Member 7: Suspended member (cannot borrow)
            Member(
                name="Sunita Verma",
                phone=f"{SEED_PHONE_PREFIX}08",
                join_date=now - timedelta(days=100),
                status=MemberStatus.SUSPENDED,
                running_fee_balance=0,
            ),
        ]
        session.add_all(members)
        session.flush()

        # 3. Items
        items = [
            # Item 0: Available cordless drill
            Item(
                name="Cordless Drill 18V [SEED-01]",
                category="Drills",
                replacement_value=450000,  # ₹4,500
                condition_note="Good condition, includes two 2Ah batteries.",
                status=ItemStatus.AVAILABLE,
            ),
            # Item 1: Fresh reservation (< 48 hours old)
            Item(
                name="Hammer Drill SDS+ [SEED-02]",
                category="Drills",
                replacement_value=800000,  # ₹8,000
                condition_note="Heavy duty, includes chuck key.",
                status=ItemStatus.RESERVED,
            ),
            # Item 2: Expired reservation (> 48 hours old, tests read-time dynamic expiry)
            Item(
                name='Circular Saw 7-1/4" [SEED-03]',
                category="Saws",
                replacement_value=550000,  # ₹5,500
                condition_note="Blade guard inspected and verified.",
                status=ItemStatus.RESERVED,
            ),
            # Item 3: Currently checked out (on time)
            Item(
                name='Compound Miter Saw 10" [SEED-04]',
                category="Saws",
                replacement_value=1400000,  # ₹14,000
                condition_note="Laser guide functional.",
                status=ItemStatus.CHECKED_OUT,
            ),
            # Item 4: Currently checked out (overdue by 3 days)
            Item(
                name="Extension Ladder 20ft [SEED-05]",
                category="Ladders",
                replacement_value=600000,  # ₹6,000
                condition_note="Aluminum, clean rungs and locks.",
                status=ItemStatus.CHECKED_OUT,
            ),
            # Item 5: Low-replacement-value item (₹150, to test replacement value cap)
            Item(
                name="Step Stool 3-Step [SEED-06]",
                category="Ladders",
                replacement_value=15000,  # ₹150 (15,000 paise)
                condition_note="Compact steel step stool.",
                status=ItemStatus.CHECKED_OUT,
            ),
            # Item 6: Currently checked out (overdue by 16 days, > 14 days threshold)
            Item(
                name="Heavy-Duty Rototiller [SEED-07]",
                category="Yard Tools",
                replacement_value=2800000,  # ₹28,000
                condition_note="Gas powered, fresh spark plug.",
                status=ItemStatus.CHECKED_OUT,
            ),
            # Item 7: Under maintenance
            Item(
                name="Outdoor Projector 1080p [SEED-08]",
                category="Projectors",
                replacement_value=2200000,  # ₹22,000
                condition_note="HDMI port loose; awaiting replacement board.",
                status=ItemStatus.UNDER_MAINTENANCE,
            ),
            # Item 8: Historical loan item
            Item(
                name='Angle Grinder 4-1/2" [SEED-09]',
                category="Saws",
                replacement_value=350000,  # ₹3,500
                condition_note="Includes spanner and safety guard.",
                status=ItemStatus.AVAILABLE,
            ),
            # Item 9: Historical loan item
            Item(
                name="Demolition Jackhammer [SEED-10]",
                category="Drills",
                replacement_value=1800000,  # ₹18,000
                condition_note="Includes pointed and flat chisels.",
                status=ItemStatus.AVAILABLE,
            ),
        ]
        session.add_all(items)
        session.flush()

        # 4. Loans
        loans = [
            # Loan 0: Active fresh reservation for Priya Patel (< 48 hours)
            Loan(
                member_id=members[1].id,
                item_id=items[1].id,
                status=LoanStatus.RESERVED,
                reserved_at=now - timedelta(hours=2),
                checked_out_at=None,
                due_at=None,
                returned_at=None,
                cancelled_at=None,
                fee_charged=0,
            ),
            # Loan 1: Expired reservation for Aarav Sharma (50 hours old > 48h)
            Loan(
                member_id=members[0].id,
                item_id=items[2].id,
                status=LoanStatus.RESERVED,
                reserved_at=now - timedelta(hours=50),
                checked_out_at=None,
                due_at=None,
                returned_at=None,
                cancelled_at=None,
                fee_charged=0,
            ),
            # Loan 2: Active on-time checkout for Vikram Singh (Loan 1 of 3)
            Loan(
                member_id=members[2].id,
                item_id=items[3].id,
                status=LoanStatus.CHECKED_OUT,
                reserved_at=now - timedelta(days=2, hours=3),
                checked_out_at=now - timedelta(days=2),
                due_at=now + timedelta(days=5),
                returned_at=None,
                cancelled_at=None,
                fee_charged=0,
            ),
            # Loan 3: Active overdue checkout for Vikram Singh (Loan 2 of 3, 3 days overdue)
            Loan(
                member_id=members[2].id,
                item_id=items[4].id,
                status=LoanStatus.CHECKED_OUT,
                reserved_at=now - timedelta(days=10, hours=2),
                checked_out_at=now - timedelta(days=10),
                due_at=now - timedelta(days=3),
                returned_at=None,
                cancelled_at=None,
                fee_charged=0,
            ),
            # Loan 4: Active on-time checkout for Vikram Singh (Loan 3 of 3, ₹150 cap test)
            Loan(
                member_id=members[2].id,
                item_id=items[5].id,
                status=LoanStatus.CHECKED_OUT,
                reserved_at=now - timedelta(days=1, hours=1),
                checked_out_at=now - timedelta(days=1),
                due_at=now + timedelta(days=6),
                returned_at=None,
                cancelled_at=None,
                fee_charged=0,
            ),
            # Loan 5: Active loan overdue by 16 days (> 14 days) for Devendra Joshi
            Loan(
                member_id=members[6].id,
                item_id=items[6].id,
                status=LoanStatus.CHECKED_OUT,
                reserved_at=now - timedelta(days=23, hours=4),
                checked_out_at=now - timedelta(days=23),
                due_at=now - timedelta(days=16),
                returned_at=None,
                cancelled_at=None,
                fee_charged=0,
            ),
            # Loan 6: Historical returned loan for Ananya Rao (fee charged: 10,000 paise = ₹100)
            Loan(
                member_id=members[3].id,
                item_id=items[8].id,
                status=LoanStatus.RETURNED,
                reserved_at=now - timedelta(days=35),
                checked_out_at=now - timedelta(days=34),
                due_at=now - timedelta(days=27),
                returned_at=now - timedelta(days=17),  # 10 days late = ₹100
                cancelled_at=None,
                fee_charged=10000,
            ),
            # Loan 7: Historical returned loan for Kavita Nair (fee charged: 10,000 paise = ₹100)
            Loan(
                member_id=members[4].id,
                item_id=items[9].id,
                status=LoanStatus.RETURNED,
                reserved_at=now - timedelta(days=25),
                checked_out_at=now - timedelta(days=24),
                due_at=now - timedelta(days=17),
                returned_at=now - timedelta(days=7),  # 10 days late = ₹100
                cancelled_at=None,
                fee_charged=10000,
            ),
            # Loan 8: Historical returned loan for Rohan Mehta (fee charged: 12,000 paise = ₹120)
            Loan(
                member_id=members[5].id,
                item_id=items[9].id,
                status=LoanStatus.RETURNED,
                reserved_at=now - timedelta(days=14),
                checked_out_at=now - timedelta(days=13),
                due_at=now - timedelta(days=6),
                returned_at=now - timedelta(days=1),  # 5 days late? No, 12 days late = ₹120
                cancelled_at=None,
                fee_charged=12000,
            ),
        ]
        session.add_all(loans)
        session.flush()

        # 5. Payments
        # Invariant for Ananya Rao: 10,000 fee - 5,000 payment = 5,000 paise (₹50 balance)
        payments = [
            Payment(
                member_id=members[3].id,
                amount=5000,
                paid_at=now - timedelta(days=10),
                note="UPI payment towards late fees",
            ),
        ]
        session.add_all(payments)
        session.flush()

        print(
            f"Successfully seeded {len(members)} members, {len(items)} items, "
            f"{len(loans)} loans, and {len(payments)} payments."
        )
        return True


if __name__ == "__main__":
    seed_database()

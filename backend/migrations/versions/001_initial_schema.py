"""Initial schema for members, items, loans, and payments.

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-10-17 19:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Members
    op.create_table(
        "members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=64), nullable=False),
        sa.Column("join_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "SUSPENDED", name="member_status"),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column(
            "running_fee_balance",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.CheckConstraint(
            "running_fee_balance >= 0",
            name="ck_members_balance_non_negative",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # 2. Items
    op.create_table(
        "items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("replacement_value", sa.Integer(), nullable=False),
        sa.Column("condition_note", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "AVAILABLE",
                "RESERVED",
                "CHECKED_OUT",
                "UNDER_MAINTENANCE",
                name="item_status",
            ),
            nullable=False,
            server_default="AVAILABLE",
        ),
        sa.CheckConstraint(
            "replacement_value > 0",
            name="ck_items_replacement_value_positive",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # 3. Loans
    op.create_table(
        "loans",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "RESERVED",
                "CHECKED_OUT",
                "RETURNED",
                "CANCELLED",
                name="loan_status",
            ),
            nullable=False,
            server_default="RESERVED",
        ),
        sa.Column("reserved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("checked_out_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("returned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fee_charged", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["members.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["items.id"],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "fee_charged >= 0",
            name="ck_loans_fee_charged_non_negative",
        ),
        sa.CheckConstraint(
            "status != 'RESERVED' OR ("
            "checked_out_at IS NULL AND due_at IS NULL AND "
            "returned_at IS NULL AND cancelled_at IS NULL)",
            name="ck_loans_reserved_timestamps",
        ),
        sa.CheckConstraint(
            "status != 'CHECKED_OUT' OR ("
            "checked_out_at IS NOT NULL AND due_at IS NOT NULL AND "
            "due_at > checked_out_at AND returned_at IS NULL AND cancelled_at IS NULL)",
            name="ck_loans_checked_out_timestamps",
        ),
        sa.CheckConstraint(
            "status != 'RETURNED' OR ("
            "checked_out_at IS NOT NULL AND due_at IS NOT NULL AND "
            "returned_at IS NOT NULL AND returned_at >= checked_out_at AND "
            "cancelled_at IS NULL)",
            name="ck_loans_returned_timestamps",
        ),
        sa.CheckConstraint(
            "status != 'CANCELLED' OR ("
            "checked_out_at IS NULL AND due_at IS NULL AND returned_at IS NULL AND "
            "cancelled_at IS NOT NULL AND cancelled_at >= reserved_at)",
            name="ck_loans_cancelled_timestamps",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_loans_member_id"), "loans", ["member_id"], unique=False)
    op.create_index(op.f("ix_loans_item_id"), "loans", ["item_id"], unique=False)

    # 4. Payments
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["members.id"],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "amount > 0",
            name="ck_payments_amount_positive",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_payments_member_id"), "payments", ["member_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_payments_member_id"), table_name="payments")
    op.drop_table("payments")
    op.drop_index(op.f("ix_loans_item_id"), table_name="loans")
    op.drop_index(op.f("ix_loans_member_id"), table_name="loans")
    op.drop_table("loans")
    op.drop_table("items")
    op.drop_table("members")
    sa.Enum(name="loan_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="item_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="member_status").drop(op.get_bind(), checkfirst=True)

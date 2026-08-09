"""Add persisted AI sourcing explanations and human review state.

Revision ID: 20260806_05
Revises: 20260730_04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260806_05"
down_revision = "20260730_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("ai_decision_explanations"):
        op.create_table(
            "ai_decision_explanations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("saved_quote_id", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(length=40), nullable=False),
            sa.Column("model", sa.String(length=120)),
            sa.Column("prompt_version", sa.String(length=40), nullable=False, server_default="quote-v1"),
            sa.Column("deterministic_snapshot", sa.JSON(), nullable=False),
            sa.Column("explanation", sa.JSON(), nullable=False),
            sa.Column("confidence", sa.Numeric(5, 4)),
            sa.Column("human_review_required", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("review_status", sa.String(length=20), nullable=False, server_default="NOT_REQUIRED"),
            sa.Column("review_note", sa.Text()),
            sa.Column("reviewed_by_user_id", sa.Integer()),
            sa.Column("reviewed_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["saved_quote_id"], ["orders_saved_quotes.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("saved_quote_id", name="uq_ai_decision_saved_quote"),
        )
    existing_indexes = {item["name"] for item in sa.inspect(bind).get_indexes("ai_decision_explanations")}
    for name, columns in (
        ("ix_ai_decision_saved_quote_id", ["saved_quote_id"]),
        ("ix_ai_decision_human_review_required", ["human_review_required"]),
        ("ix_ai_decision_review_status", ["review_status"]),
        ("ix_ai_decision_reviewed_by_user_id", ["reviewed_by_user_id"]),
        ("ix_ai_decision_reviewed_at", ["reviewed_at"]),
        ("ix_ai_decision_created_at", ["created_at"]),
    ):
        if name not in existing_indexes:
            op.create_index(name, "ai_decision_explanations", columns)


def downgrade() -> None:
    op.drop_table("ai_decision_explanations")

"""Add persisted candidate proposals and evaluation/review records."""
from alembic import op
import sqlalchemy as sa

revision = "0002_candidates"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("scenario_id", sa.String(36), nullable=False),
        sa.Column("hypothesis", sa.Text(), nullable=False),
        sa.Column("proposed_change", sa.Text(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("production_applied", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scenario_id"], ["scenarios.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_candidates_project_created", "candidates", ["project_id", "created_at"])
    op.create_table(
        "candidate_evaluations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("candidate_id", sa.String(36), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence_mode", sa.String(20), nullable=False),
        sa.Column("target_passed", sa.Boolean(), nullable=False),
        sa.Column("regression_count", sa.Integer(), nullable=False),
        sa.Column("failed_regressions", sa.JSON(), nullable=False),
        sa.Column("critical_regressions", sa.JSON(), nullable=False),
        sa.Column("checks_snapshot", sa.JSON(), nullable=False),
        sa.Column("review_decision", sa.String(20), nullable=True),
        sa.Column("reviewer", sa.String(120), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_candidate_evaluations_candidate_created",
        "candidate_evaluations",
        ["candidate_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_candidate_evaluations_candidate_created", table_name="candidate_evaluations")
    op.drop_table("candidate_evaluations")
    op.drop_index("ix_candidates_project_created", table_name="candidates")
    op.drop_table("candidates")

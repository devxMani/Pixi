"""Add retry-safe idempotency metadata to run records."""

from alembic import op
import sqlalchemy as sa


revision = "0003_run_idempotency"
down_revision = "0002_candidates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("idempotency_key", sa.String(length=200), nullable=True))
    op.add_column("runs", sa.Column("idempotency_fingerprint", sa.String(length=64), nullable=True))
    op.create_index(
        "uq_runs_idempotency_key",
        "runs",
        ["project_id", "scenario_id", "idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_runs_idempotency_key", table_name="runs")
    op.drop_column("runs", "idempotency_fingerprint")
    op.drop_column("runs", "idempotency_key")

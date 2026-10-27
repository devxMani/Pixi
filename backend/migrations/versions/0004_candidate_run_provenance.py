"""Record candidate variant and immutable agent version with each run."""

from alembic import op
import sqlalchemy as sa


revision = "0004_candidate_run_provenance"
down_revision = "0003_run_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Keep candidate_id as immutable provenance rather than adding a new FK
    # constraint to the historical runs table. SQLite cannot ALTER in a new FK,
    # and batch-recreating runs fails on older unnamed constraints.
    op.add_column("runs", sa.Column("candidate_id", sa.String(length=36), nullable=True))
    op.add_column(
        "runs",
        sa.Column(
            "variant",
            sa.String(length=20),
            server_default="simulated",
            nullable=False,
        ),
    )
    op.add_column("runs", sa.Column("agent_version", sa.String(length=200), nullable=True))
    op.create_index(
        "ix_runs_candidate_variant_started",
        "runs",
        ["candidate_id", "variant", "started_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_runs_candidate_variant_started", table_name="runs")
    op.drop_column("runs", "agent_version")
    op.drop_column("runs", "variant")
    op.drop_column("runs", "candidate_id")

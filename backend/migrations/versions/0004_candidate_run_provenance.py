"""Record candidate variant and immutable agent version with each run."""

from alembic import op
import sqlalchemy as sa


revision = "0004_candidate_run_provenance"
down_revision = "0003_run_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("runs", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column(
                "candidate_id",
                sa.String(length=36),
                sa.ForeignKey("candidates.id", ondelete="SET NULL"),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "variant",
                sa.String(length=20),
                server_default="simulated",
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("agent_version", sa.String(length=200), nullable=True))

    op.create_index(
        "ix_runs_candidate_variant_started",
        "runs",
        ["candidate_id", "variant", "started_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_runs_candidate_variant_started", table_name="runs")
    with op.batch_alter_table("runs", recreate="always") as batch_op:
        batch_op.drop_column("agent_version")
        batch_op.drop_column("variant")
        batch_op.drop_column("candidate_id")

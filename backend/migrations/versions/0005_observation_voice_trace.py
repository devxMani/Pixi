"""Persist structured per-turn voice trace on observation records."""

from alembic import op
import sqlalchemy as sa


revision = "0005_observation_voice_trace"
down_revision = "0004_candidate_run_provenance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "observations",
        sa.Column("voice_trace", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("observations", "voice_trace")

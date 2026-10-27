"""Create initial Pixi persistence schema."""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "scenarios",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_scenarios_project_created", "scenarios", ["project_id", "created_at"])
    op.create_table(
        "runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("scenario_id", sa.String(length=36), nullable=False),
        sa.Column("adapter_name", sa.String(length=100), nullable=False),
        sa.Column("evidence_mode", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("scenario_snapshot", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scenario_id"], ["scenarios.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_runs_project_started", "runs", ["project_id", "started_at"])
    op.create_index("ix_runs_scenario_started", "runs", ["scenario_id", "started_at"])
    op.create_table(
        "observations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("transcript", sa.Text(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("tools_called", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("evidence_mode", sa.String(length=20), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_observations_run_created", "observations", ["run_id", "created_at"])
    op.create_table(
        "run_checks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("assertion_id", sa.String(length=120), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("run_checks")
    op.drop_index("ix_observations_run_created", table_name="observations")
    op.drop_table("observations")
    op.drop_index("ix_runs_scenario_started", table_name="runs")
    op.drop_index("ix_runs_project_started", table_name="runs")
    op.drop_table("runs")
    op.drop_index("ix_scenarios_project_created", table_name="scenarios")
    op.drop_table("scenarios")
    op.drop_table("projects")

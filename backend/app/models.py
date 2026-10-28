"""Initial persisted entities for projects, scenarios, and evidence runs."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


class ProjectRecord(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    scenarios: Mapped[list[ScenarioRecord]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class ScenarioRecord(Base):
    __tablename__ = "scenarios"
    __table_args__ = (Index("ix_scenarios_project_created", "project_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    definition: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    project: Mapped[ProjectRecord] = relationship(back_populates="scenarios")
    runs: Mapped[list[RunRecord]] = relationship(back_populates="scenario")


class RunRecord(Base):
    __tablename__ = "runs"
    __table_args__ = (
        Index("ix_runs_project_started", "project_id", "started_at"),
        Index("ix_runs_scenario_started", "scenario_id", "started_at"),
        Index("ix_runs_candidate_variant_started", "candidate_id", "variant", "started_at"),
        Index("uq_runs_idempotency_key", "project_id", "scenario_id", "idempotency_key", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    scenario_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scenarios.id", ondelete="RESTRICT"), nullable=False
    )
    adapter_name: Mapped[str] = mapped_column(String(100), nullable=False)
    evidence_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    scenario_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    idempotency_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Historical provenance ID; intentionally not a foreign key so candidate
    # cleanup cannot rewrite old run records and SQLite can add the column in place.
    candidate_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    variant: Mapped[str] = mapped_column(String(20), nullable=False, default="simulated")
    agent_version: Mapped[str | None] = mapped_column(String(200), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    scenario: Mapped[ScenarioRecord] = relationship(back_populates="runs")
    observations: Mapped[list[ObservationRecord]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    checks: Mapped[list[CheckRecord]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class ObservationRecord(Base):
    __tablename__ = "observations"
    __table_args__ = (Index("ix_observations_run_created", "run_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    transcript: Mapped[str] = mapped_column(Text, nullable=False, default="")
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    tools_called: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    voice_trace: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    run: Mapped[RunRecord] = relationship(back_populates="observations")


class CheckRecord(Base):
    __tablename__ = "run_checks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    assertion_id: Mapped[str] = mapped_column(String(120), nullable=False)
    passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped[RunRecord] = relationship(back_populates="checks")



class CandidateRecord(Base):
    __tablename__ = "candidates"
    __table_args__ = (Index("ix_candidates_project_created", "project_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    scenario_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scenarios.id", ondelete="RESTRICT"), nullable=False
    )
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_change: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="proposed")
    production_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    evaluations: Mapped[list[CandidateEvaluationRecord]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )


class CandidateEvaluationRecord(Base):
    __tablename__ = "candidate_evaluations"
    __table_args__ = (
        Index("ix_candidate_evaluations_candidate_created", "candidate_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    candidate_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False
    )
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    target_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    regression_count: Mapped[int] = mapped_column(Integer, nullable=False)
    failed_regressions: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    critical_regressions: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    checks_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    review_decision: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reviewer: Mapped[str | None] = mapped_column(String(120), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    candidate: Mapped[CandidateRecord] = relationship(back_populates="evaluations")

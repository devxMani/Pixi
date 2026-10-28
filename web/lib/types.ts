export type EvidenceMode = "simulated" | "live";
export type RunVariant = "simulated" | "baseline" | "candidate";
export type RunStatus = "passed" | "failed" | "inconclusive";
export type EvaluationOutcome =
  | "passed"
  | "failed"
  | "inconclusive"
  | "invalid_setup"
  | "not_applicable";

export interface Project {
  id: string;
  name: string;
  created_at: string;
}

export type AssertionKind =
  | "contains"
  | "not_contains"
  | "max_latency_ms"
  | "tool_called"
  | "tool_not_called";

export interface ScenarioAssertion {
  id: string;
  kind: AssertionKind;
  expected_text?: string | null;
  threshold_ms?: number | null;
  tool_name?: string | null;
  critical?: boolean;
}

export interface ScenarioDefinition {
  id: string;
  name: string;
  turns: string[];
  assertions: ScenarioAssertion[];
}

export interface ScenarioRecord {
  id: string;
  project_id: string;
  name: string;
  definition: ScenarioDefinition;
  created_at: string;
}

export interface Observation {
  id: string;
  transcript: string;
  latency_ms: number | null;
  tools_called: string[];
  error: string | null;
  evidence_mode: EvidenceMode;
  provider: string | null;
  model: string | null;
  created_at: string;
}

export interface Check {
  id: string;
  sequence: number;
  assertion_id: string;
  passed: boolean | null;
  error: string | null;
}

export interface RunRecord {
  id: string;
  project_id: string;
  scenario_id: string;
  adapter_name: string;
  evidence_mode: EvidenceMode;
  variant: RunVariant;
  candidate_id: string | null;
  agent_version: string | null;
  status: RunStatus;
  scenario_snapshot: ScenarioDefinition;
  started_at: string;
  finished_at: string;
  observations: Observation[];
  checks: Check[];
}

export interface Evaluation {
  id: string;
  outcome: EvaluationOutcome;
  reason: string;
  evidence_mode: EvidenceMode;
  target_passed: boolean | null;
  regression_count: number;
  failed_regressions: string[];
  critical_regressions: string[];
  checks_snapshot: Record<string, unknown>;
  review_decision: "accept" | "reject" | null;
  reviewer: string | null;
  review_note: string | null;
  reviewed_at: string | null;
  created_at: string;
}

export interface Candidate {
  id: string;
  project_id: string;
  scenario_id: string;
  hypothesis: string;
  proposed_change: string;
  status: string;
  production_applied: boolean;
  created_at: string;
  latest_evaluation: Evaluation | null;
}

export interface ApiErrorPayload {
  detail?: string;
  message?: string;
}

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

export interface VoiceTraceTool {
  name: string;
  arguments: Record<string, unknown>;
  output: string | null;
  latency_ms: number | null;
  success: boolean;
  error: string | null;
}

export interface VoiceTraceLatency {
  stt_processing_ms: number | null;
  eot_latency_ms: number | null;
  llm_ttft_ms: number | null;
  tts_ttfb_ms: number | null;
  e2e_ms: number | null;
}

export interface VoiceTraceInterruption {
  interrupted: boolean;
  overlapping_speech: boolean;
  false_interruption: boolean;
  detection_delay_ms: number | null;
  agent_speech_duration_ms: number | null;
  recovered: boolean;
}

export interface VoiceTraceTurn {
  user_input: string;
  assistant_output: string;
  tools: VoiceTraceTool[];
  latency: VoiceTraceLatency;
  interruption: VoiceTraceInterruption;
  interrupted: boolean;
  status: string;
  error: string | null;
}

export interface VoiceTrace {
  trace_started_at?: string;
  input_mode?: "text" | "audio" | string;
  latency_basis?: string;
  agent_version?: string;
  candidate_id?: string | null;
  measured_turn_count?: number;
  scenario_elapsed_ms?: number;
  status: string;
  error: string | null;
  turns: VoiceTraceTurn[];
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
  voice_trace?: VoiceTrace | null;
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

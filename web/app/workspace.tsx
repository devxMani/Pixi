"use client";

import {
  Activity, ArrowDownToLine, ArrowLeftRight, AudioLines, BadgeCheck, Check, CheckCircle2,
  ChevronDown, CircleHelp, Code2, Database, Download, ExternalLink, FileJson,
  FlaskConical, Gauge, GitBranch, Layers3, LoaderCircle, LockKeyhole, Plus, RefreshCw,
  ShieldCheck, Sparkles, Upload, X, XCircle, Zap,
} from "lucide-react";
import {
  useCallback, useEffect, useMemo, useRef, useState,
  type ChangeEvent, type FormEvent, type ReactNode,
} from "react";

import { api, getProjectWorkspace, getProjects, newIdempotencyKey } from "@/lib/api";
import type {
  Candidate, Project, RunRecord, ScenarioAssertion, ScenarioRecord,
} from "@/lib/types";

type View = "overview" | "scenarios" | "runs" | "candidates" | "setup";
type Notice = { kind: "info" | "success" | "error"; text: string } | null;

const NAV = [
  { id: "overview", label: "Overview", icon: Gauge },
  { id: "scenarios", label: "Scenarios", icon: Layers3 },
  { id: "runs", label: "Run history", icon: Activity },
  { id: "candidates", label: "Candidates", icon: GitBranch },
  { id: "setup", label: "Setup & docs", icon: Code2 },
] as const;

const DEFAULT_ASSERTIONS = JSON.stringify([
  { id: "mentions-price", kind: "contains", expected_text: "$20", critical: false },
  { id: "no-secret-disclosure", kind: "not_contains", expected_text: "internal secret", critical: true },
], null, 2);

const PAGE_COPY: Record<View, { eyebrow: string; title: string; description: string }> = {
  overview: {
    eyebrow: "Reliability workspace",
    title: "Know what broke. Prove what fixed it.",
    description: "A single evidence trail for scenario runs, agent versions, and conservative candidate decisions.",
  },
  scenarios: {
    eyebrow: "Test design",
    title: "Scenarios",
    description: "Define repeatable user turns and explicit checks. Critical assertions are highlighted in every saved evaluation.",
  },
  runs: {
    eyebrow: "Evidence",
    title: "Run history",
    description: "Inspect the transcript, assertion results, provenance, and agent version behind every saved run.",
  },
  candidates: {
    eyebrow: "Improvement loop",
    title: "Candidate changes",
    description: "Keep the hypothesis explicit, test a pinned candidate version across the project, and require saved evidence before review.",
  },
  setup: {
    eyebrow: "Developer setup",
    title: "Connect your agent",
    description: "Pixi keeps provider credentials server-side and treats the configured bridge as the boundary to your actual runtime.",
  },
};

function nice(value: string | null | undefined): string {
  if (!value) return "—";
  return value.replaceAll("_", " ").split(" ").map((part) => part ? part[0].toUpperCase() + part.slice(1) : part).join(" ");
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : new Intl.DateTimeFormat(undefined, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  }).format(parsed);
}

function StatusPill({ value }: { value: string }) {
  const className = value.toLowerCase().replace(/[^a-z0-9_-]/g, "_");
  return <span className={"pill " + className}>{nice(value)}</span>;
}

function EmptyState({ icon, title, description, action }: {
  icon?: ReactNode; title: string; description: string; action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      {icon ? <div className="callout-icon">{icon}</div> : null}
      <strong>{title}</strong><p>{description}</p>{action}
    </div>
  );
}

function NoticeBar({ notice, onDismiss }: { notice: NonNullable<Notice>; onDismiss: () => void }) {
  const Icon = notice.kind === "error" ? XCircle : notice.kind === "success" ? CheckCircle2 : CircleHelp;
  return (
    <div className={"notice " + notice.kind} role={notice.kind === "error" ? "alert" : "status"}>
      <span className="notice-icon"><Icon size={15} /></span>
      <div style={{ flex: 1 }}>{notice.text}</div>
      <button className="btn ghost small" type="button" aria-label="Dismiss notice" onClick={onDismiss}><X size={13} /></button>
    </div>
  );
}

function MetricCard({ label, value, foot, tone = "accent" }: {
  label: string; value: number | string; foot: string; tone?: "accent" | "green" | "amber" | "red";
}) {
  return <div className="metric-card"><div className="metric-label">{label}</div><div className={"metric-value metric-" + tone}>{value}</div><div className="metric-foot">{foot}</div></div>;
}

function CheckList({ run }: { run: RunRecord }) {
  if (!run.checks.length) return <p className="hint">No assertion records were saved for this run.</p>;
  return (
    <div className="check-list">
      {run.checks.map((check) => {
        const kind = check.passed === true ? "pass" : check.passed === false ? "fail" : "unknown";
        const symbol = check.passed === true ? <Check size={11} /> : check.passed === false ? <X size={11} /> : "·";
        const assertion = run.scenario_snapshot.assertions.find((item) => item.id === check.assertion_id);
        return (
          <div className="check-item" key={check.id}>
            <div className={"check-mark " + kind}>{symbol}</div>
            <div className="check-copy">
              <strong>{check.assertion_id}{assertion && assertion.critical ? " · CRITICAL" : ""}</strong>
              <p>{check.error || (check.passed === null ? "Evidence unavailable" : check.passed ? "Assertion passed" : "Assertion failed")}</p>
            </div>
            <StatusPill value={check.passed === true ? "passed" : check.passed === false ? "failed" : "inconclusive"} />
          </div>
        );
      })}
    </div>
  );
}

function RunDetail({ run }: { run: RunRecord }) {
  const observation = run.observations[0];
  return (
    <div className="run-detail">
      <div className="detail-grid">
        <div className="detail-cell"><span>Result</span><strong>{nice(run.status)}</strong></div>
        <div className="detail-cell"><span>Evidence</span><strong>{nice(run.evidence_mode)}</strong></div>
        <div className="detail-cell"><span>Variant</span><strong>{nice(run.variant)}</strong></div>
        <div className="detail-cell"><span>Agent version</span><strong>{run.agent_version || "Missing"}</strong></div>
        <div className="detail-cell"><span>Latency</span><strong>{observation && observation.latency_ms != null ? Math.round(observation.latency_ms) + " ms" : "Unavailable"}</strong></div>
        <div className="detail-cell"><span>Adapter</span><strong>{run.adapter_name}</strong></div>
      </div>
      {run.candidate_id ? <div className="evidence-block"><h3>Candidate reference</h3><code className="mono wrap">{run.candidate_id}</code></div> : null}
      <div className="evidence-block">
        <h3>Observed transcript</h3>
        {observation && observation.transcript ? <pre className="transcript">{observation.transcript}</pre> : <p className="hint">No transcript was returned.</p>}
        {observation && observation.error ? <p className="hint" style={{ color: "var(--red)" }}>Adapter error: {observation.error}</p> : null}
        <p className="hint">
          {observation && observation.provider ? "Provider: " + observation.provider : "Provider not reported"}
          {observation && observation.model ? " · Model: " + observation.model : ""}
          {observation && observation.tools_called.length ? " · Tools: " + observation.tools_called.join(", ") : ""}
        </p>
      </div>
      {observation && observation.voice_trace ? (
        <div className="evidence-block">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h3>Structured voice trace</h3>
            <StatusPill value={observation.voice_trace.status} />
          </div>
          <p className="hint">
            Input mode: {observation.voice_trace.input_mode || "not reported"}
            {" · "}
            Latency basis: {observation.voice_trace.latency_basis || "not reported"}
            {" · "}
            Turns: {observation.voice_trace.measured_turn_count ?? observation.voice_trace.turns.length}
          </p>
          {observation.voice_trace.input_mode === "text" ? (
            <div className="notice info">
              <AudioLines size={14} />
              <span>
                This run used scripted text input through the real LiveKit agent session.
                Its response time is text-input-to-response timing, not microphone-to-audio
                latency. STT, acoustic endpointing, VAD and barge-in metrics are only shown
                when the runtime actually emits them.
              </span>
            </div>
          ) : null}
          {observation.voice_trace.error ? (
            <p className="hint" style={{ color: "var(--red)" }}>Trace error: {observation.voice_trace.error}</p>
          ) : null}
          <div className="list">
            {observation.voice_trace.turns.map((turn, index) => (
              <div className="evidence-block" key={index}>
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <h3>Turn {index + 1}</h3>
                  <StatusPill value={turn.status} />
                </div>
                <div className="field">
                  <label>User input</label>
                  <pre className="transcript">{turn.user_input || "Not recorded"}</pre>
                </div>
                <div className="field">
                  <label>Assistant output</label>
                  <pre className="transcript">{turn.assistant_output || "No assistant text recorded"}</pre>
                </div>
                {turn.error ? <p className="hint" style={{ color: "var(--red)" }}>Turn error: {turn.error}</p> : null}
                <div className="detail-grid">
                  {([
                    ["STT processing", turn.latency.stt_processing_ms],
                    ["End-of-utterance delay", turn.latency.eot_latency_ms],
                    ["LLM time to first token", turn.latency.llm_ttft_ms],
                    ["TTS time to first byte", turn.latency.tts_ttfb_ms],
                    ["Turn response time", turn.latency.e2e_ms],
                  ] as const).map(([label, value]) => (
                    <div className="detail-cell" key={label}>
                      <span>{label}</span>
                      <strong>{value == null ? "Unavailable" : Math.round(value) + " ms"}</strong>
                    </div>
                  ))}
                </div>
                {turn.tools.length ? (
                  <div className="evidence-block" style={{ marginTop: 12 }}>
                    <h3>Tool events</h3>
                    {turn.tools.map((tool, toolIndex) => (
                      <div className="check-item" key={tool.name + "-" + toolIndex}>
                        <div className={"check-mark " + (tool.success ? "pass" : "fail")}>
                          {tool.success ? <Check size={11} /> : <X size={11} />}
                        </div>
                        <div className="check-copy">
                          <strong>{tool.name} · {tool.latency_ms == null ? "latency unavailable" : Math.round(tool.latency_ms) + " ms"}</strong>
                          <p>{tool.error || tool.output || (tool.success ? "Tool call completed" : "Tool call failed")}</p>
                          {Object.keys(tool.arguments || {}).length ? (
                            <pre className="transcript">{JSON.stringify(tool.arguments, null, 2)}</pre>
                          ) : null}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : <p className="hint">No tool events were recorded for this turn.</p>}
                <div className="row" style={{ flexWrap: "wrap" }}>
                  <StatusPill value={turn.interruption.interrupted ? "interrupted" : "not interrupted"} />
                  <StatusPill value={turn.interruption.overlapping_speech ? "overlapping speech" : "no overlap reported"} />
                  <StatusPill value={turn.interruption.recovered ? "recovered" : "recovery not reported"} />
                </div>
                {turn.interruption.detection_delay_ms != null || turn.interruption.agent_speech_duration_ms != null ? (
                  <p className="hint">
                    Interruption detection: {turn.interruption.detection_delay_ms == null ? "unavailable" : Math.round(turn.interruption.detection_delay_ms) + " ms"}
                    {" · "}
                    Agent speech duration: {turn.interruption.agent_speech_duration_ms == null ? "unavailable" : Math.round(turn.interruption.agent_speech_duration_ms) + " ms"}
                  </p>
                ) : null}
              </div>
            ))}
          </div>
          <details style={{ marginTop: 12 }}>
            <summary style={{ cursor: "pointer", color: "var(--muted)", fontSize: 11, fontWeight: 700 }}>Raw structured trace JSON</summary>
            <pre className="transcript">{JSON.stringify(observation.voice_trace, null, 2)}</pre>
          </details>
        </div>
      ) : null}
      <div className="evidence-block"><h3>Assertion evidence</h3><CheckList run={run} /></div>
    </div>
  );
}

export default function Workspace() {
  const [view, setView] = useState<View>("overview");
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [scenarios, setScenarios] = useState<ScenarioRecord[]>([]);
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [selectedScenarioId, setSelectedScenarioId] = useState("");
  const [selectedRunId, setSelectedRunId] = useState("");
  const [selectedCandidateId, setSelectedCandidateId] = useState("");
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [suiteProgress, setSuiteProgress] = useState("");
  const [notice, setNotice] = useState<Notice>(null);
  const [showProjectModal, setShowProjectModal] = useState(false);
  const [projectName, setProjectName] = useState("");
  const [scenarioName, setScenarioName] = useState("Pricing question");
  const [scenarioTurns, setScenarioTurns] = useState("How much does the basic plan cost?");
  const [assertionsJson, setAssertionsJson] = useState(DEFAULT_ASSERTIONS);
  const [fixtureTranscript, setFixtureTranscript] = useState("The basic plan costs $20 per month.");
  const [fixtureLatency, setFixtureLatency] = useState("420");
  const [candidateTargetScenarioId, setCandidateTargetScenarioId] = useState("");
  const [hypothesis, setHypothesis] = useState("");
  const [proposedChange, setProposedChange] = useState("");
  const [reviewer, setReviewer] = useState("Local reviewer");
  const [reviewNote, setReviewNote] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pendingKeys = useRef(new Map<string, string>());

  const project = projects.find((item) => item.id === projectId) ?? null;
  const selectedScenario = scenarios.find((item) => item.id === selectedScenarioId) ?? null;
  const selectedCandidate = candidates.find((item) => item.id === selectedCandidateId) ?? null;
  const selectedRun = runs.find((item) => item.id === selectedRunId) ?? null;
  const page = PAGE_COPY[view];

  const refreshWorkspace = useCallback(async (id: string, focusRunId?: string, focusCandidateId?: string) => {
    const data = await getProjectWorkspace(id);
    setScenarios(data.scenarios);
    setRuns(data.runs);
    setCandidates(data.candidates);
    setSelectedScenarioId((current) => data.scenarios.some((item) => item.id === current) ? current : data.scenarios[0]?.id ?? "");
    setSelectedRunId((current) => focusRunId && data.runs.some((item) => item.id === focusRunId)
      ? focusRunId
      : data.runs.some((item) => item.id === current) ? current : data.runs[0]?.id ?? "");
    setSelectedCandidateId((current) => focusCandidateId && data.candidates.some((item) => item.id === focusCandidateId)
      ? focusCandidateId
      : data.candidates.some((item) => item.id === current) ? current : data.candidates[0]?.id ?? "");
    setCandidateTargetScenarioId((current) => data.scenarios.some((item) => item.id === current) ? current : data.scenarios[0]?.id ?? "");
    setConnected(true);
    return data;
  }, []);

  const refreshProjectList = useCallback(async (preferId?: string) => {
    const data = await getProjects();
    setProjects(data);
    setConnected(true);
    setProjectId((current) => preferId && data.some((item) => item.id === preferId)
      ? preferId
      : data.some((item) => item.id === current) ? current : data[0]?.id ?? "");
    return data;
  }, []);

  useEffect(() => {
    let active = true;
    getProjects()
      .then((data) => {
        if (!active) return;
        setProjects(data);
        setProjectId(data[0]?.id ?? "");
        setConnected(true);
        setNotice(data.length ? null : { kind: "info", text: "Pixi is connected. Create a project to save scenarios and evidence." });
      })
      .catch((error: unknown) => {
        if (!active) return;
        setConnected(false);
        setNotice({ kind: "error", text: error instanceof Error ? error.message : "Could not connect to Pixi. Start FastAPI with APP_ENV=development." });
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    if (!projectId) {
      return () => { active = false; };
    }
    getProjectWorkspace(projectId)
      .then((data) => {
        if (!active) return;
        setScenarios(data.scenarios);
        setRuns(data.runs);
        setCandidates(data.candidates);
        setSelectedScenarioId((current) => data.scenarios.some((item) => item.id === current) ? current : data.scenarios[0]?.id ?? "");
        setSelectedRunId((current) => data.runs.some((item) => item.id === current) ? current : data.runs[0]?.id ?? "");
        setSelectedCandidateId((current) => data.candidates.some((item) => item.id === current) ? current : data.candidates[0]?.id ?? "");
        setCandidateTargetScenarioId((current) => data.scenarios.some((item) => item.id === current) ? current : data.scenarios[0]?.id ?? "");
        setConnected(true);
      })
      .catch((error: unknown) => {
        if (!active) return;
        setNotice({ kind: "error", text: error instanceof Error ? error.message : "Could not load this project." });
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [projectId]);

  const sortedRuns = useMemo(
    () => [...runs].sort((a, b) => Date.parse(b.started_at) - Date.parse(a.started_at)),
    [runs],
  );
  const sortedCandidates = useMemo(
    () => [...candidates].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at)),
    [candidates],
  );
  const failedCount = runs.filter((run) => run.status === "failed").length;
  const liveCount = runs.filter((run) => run.evidence_mode === "live").length;

  function stableKey(scope: string): string {
    const existing = pendingKeys.current.get(scope);
    if (existing) return existing;
    const key = newIdempotencyKey();
    pendingKeys.current.set(scope, key);
    return key;
  }

  async function onCreateProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = projectName.trim();
    if (!name) return;
    setBusy("create-project");
    setNotice(null);
    try {
      const created = await api<Project>("projects", { method: "POST", body: { name } });
      setProjects((current) => [created, ...current]);
      setLoading(true);
      setProjectId(created.id);
      setProjectName("");
      setShowProjectModal(false);
      setView("overview");
      setNotice({ kind: "success", text: "Project “" + created.name + "” created." });
    } catch (error) {
      setNotice({ kind: "error", text: error instanceof Error ? error.message : "Could not create the project." });
    } finally {
      setBusy("");
    }
  }

  async function onCreateScenario(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!projectId) {
      setNotice({ kind: "info", text: "Create a project before adding scenarios." });
      return;
    }
    setBusy("create-scenario");
    setNotice(null);
    try {
      const turns = scenarioTurns.split("\n").map((turn) => turn.trim()).filter(Boolean);
      const assertions = JSON.parse(assertionsJson) as ScenarioAssertion[];
      if (!turns.length) throw new Error("Add at least one user turn.");
      if (!Array.isArray(assertions) || !assertions.length) throw new Error("Assertions must be a non-empty JSON array.");
      const created = await api<ScenarioRecord>(
        "projects/" + encodeURIComponent(projectId) + "/scenarios",
        { method: "POST", body: { name: scenarioName.trim(), turns, assertions } },
      );
      await refreshWorkspace(projectId);
      setSelectedScenarioId(created.id);
      setCandidateTargetScenarioId(created.id);
      setView("scenarios");
      setNotice({ kind: "success", text: "Scenario “" + created.name + "” saved. It is now part of the project regression suite." });
    } catch (error) {
      setNotice({ kind: "error", text: error instanceof Error ? error.message : "Could not create the scenario." });
    } finally {
      setBusy("");
    }
  }

  async function runScenario(scenarioId: string, variant: "baseline" | "candidate" | "fixture", candidateId?: string) {
    if (!projectId) return;
    const scenario = scenarios.find((item) => item.id === scenarioId);
    if (!scenario) {
      setNotice({ kind: "error", text: "Choose a saved scenario first." });
      return;
    }
    const projectAtStart = projectId;
    const scope = projectAtStart + ":" + scenarioId + ":" + variant + ":" + (candidateId ?? "none");
    const key = stableKey(scope);
    setBusy(variant === "fixture" ? "fixture-run" : "run-" + variant);
    setNotice(null);
    try {
      let run: RunRecord;
      if (variant === "fixture") {
        const latencyValue = fixtureLatency.trim() ? Number(fixtureLatency) : null;
        if (latencyValue !== null && (!Number.isFinite(latencyValue) || latencyValue < 0)) {
          throw new Error("Latency must be a non-negative number.");
        }
        run = await api<RunRecord>(
          "projects/" + encodeURIComponent(projectAtStart) + "/scenarios/" + encodeURIComponent(scenarioId) + "/demo-runs",
          {
            method: "POST",
            headers: { "Idempotency-Key": key },
            body: { transcript: fixtureTranscript, latency_ms: latencyValue, tools_called: [] },
          },
        );
      } else {
        const query = variant === "candidate" && candidateId ? "?candidate_id=" + encodeURIComponent(candidateId) : "";
        run = await api<RunRecord>(
          "projects/" + encodeURIComponent(projectAtStart) + "/scenarios/" + encodeURIComponent(scenarioId) + "/agent-runs" + query,
          { method: "POST", headers: { "Idempotency-Key": key } },
        );
      }
      await refreshWorkspace(projectAtStart, run.id, candidateId);
      pendingKeys.current.delete(scope);
      setView("runs");
      setNotice({
        kind: run.status === "passed" ? "success" : "info",
        text: "Run saved: " + nice(run.status) + " · " + nice(run.evidence_mode) + " · " + nice(run.variant) + " · version " + (run.agent_version || "missing") + ".",
      });
    } catch (error) {
      setNotice({ kind: "error", text: (error instanceof Error ? error.message : "Run failed.") + " The retry key is retained when the server response could be ambiguous." });
    } finally {
      setBusy("");
    }
  }

  async function runCandidateSuite(candidate: Candidate) {
    if (!projectId || !scenarios.length) {
      setNotice({ kind: "info", text: "Add at least one scenario before running a candidate suite." });
      return;
    }
    const projectAtStart = projectId;
    const scenarioSnapshot = [...scenarios];
    const total = scenarioSnapshot.length;
    setBusy("candidate-suite");
    setNotice(null);
    const completed: RunRecord[] = [];
    try {
      for (let index = 0; index < total; index += 1) {
        const scenario = scenarioSnapshot[index];
        const scope = projectAtStart + ":" + candidate.id + ":suite:" + scenario.id;
        const key = stableKey(scope);
        setSuiteProgress((index + 1) + " / " + total + " · " + scenario.name);
        const run = await api<RunRecord>(
          "projects/" + encodeURIComponent(projectAtStart) + "/scenarios/" + encodeURIComponent(scenario.id) + "/agent-runs?candidate_id=" + encodeURIComponent(candidate.id),
          { method: "POST", headers: { "Idempotency-Key": key } },
        );
        completed.push(run);
      }
      const lastRun = completed[completed.length - 1];
      await refreshWorkspace(projectAtStart, lastRun?.id, candidate.id);
      scenarioSnapshot.forEach((scenario) => pendingKeys.current.delete(projectAtStart + ":" + candidate.id + ":suite:" + scenario.id));
      setView("runs");
      const passed = completed.filter((run) => run.status === "passed").length;
      const failed = completed.filter((run) => run.status === "failed").length;
      const inconclusive = completed.filter((run) => run.status === "inconclusive").length;
      const versions = Array.from(new Set(completed.map((run) => run.agent_version).filter(Boolean)));
      const consistent = completed.every((run) => run.candidate_id === candidate.id && run.variant === "candidate" && Boolean(run.agent_version));
      const clean = failed === 0 && inconclusive === 0 && versions.length === 1 && consistent;
      setNotice({
        kind: clean ? "success" : "info",
        text: "Candidate suite saved " + completed.length + " run(s): " + passed + " passed, " + failed + " failed, " + inconclusive + " inconclusive. Candidate version: " + (versions.length === 1 ? versions[0] : versions.length === 0 ? "missing" : "inconsistent") + ". " + (clean ? "Now evaluate it against a failed baseline." : "Inspect failures and version provenance before evaluating."),
      });
    } catch (error) {
      setNotice({ kind: "error", text: "Candidate suite stopped after " + completed.length + " of " + total + " requests. Saved runs remain in history; retry reuses each scenario's idempotency key. " + (error instanceof Error ? error.message : "Request failed.") });
    } finally {
      setBusy("");
      setSuiteProgress("");
    }
  }

  function evidenceForCandidate(candidate: Candidate) {
    const latest = (predicate: (run: RunRecord) => boolean) => sortedRuns.find(predicate) ?? null;
    const baseline = latest((run) =>
      run.evidence_mode === "live" && run.variant === "baseline" && !run.candidate_id && run.scenario_id === candidate.scenario_id,
    );
    const target = latest((run) =>
      run.evidence_mode === "live" && run.variant === "candidate" && run.candidate_id === candidate.id && run.scenario_id === candidate.scenario_id,
    );
    const regressions = scenarios
      .filter((scenario) => scenario.id !== candidate.scenario_id)
      .map((scenario) => ({
        scenario,
        run: latest((run) =>
          run.evidence_mode === "live" && run.variant === "candidate" && run.candidate_id === candidate.id && run.scenario_id === scenario.id,
        ),
      }));
    return { baseline, target, regressions, missingRegressions: regressions.filter((item) => item.run === null) };
  }

  async function evaluateSelectedCandidate() {
    if (!projectId || !selectedCandidate) return;
    const evidence = evidenceForCandidate(selectedCandidate);
    if (!evidence.baseline || evidence.baseline.status !== "failed") {
      setNotice({ kind: "error", text: "A live baseline run for the target scenario must fail first. Run the baseline again and inspect its assertions." });
      return;
    }
    if (!evidence.target) {
      setNotice({ kind: "error", text: "Run the selected candidate against its target scenario first." });
      return;
    }
    if (evidence.missingRegressions.length) {
      setNotice({ kind: "error", text: "Regression suite incomplete. Run the candidate against: " + evidence.missingRegressions.map((item) => item.scenario.name).join(", ") + "." });
      return;
    }
    if (!evidence.regressions.length) {
      setNotice({ kind: "error", text: "Add at least one non-target scenario so Pixi can measure regression risk." });
      return;
    }
    setBusy("evaluate-candidate");
    setNotice(null);
    try {
      const evaluated = await api<Candidate>(
        "candidates/" + encodeURIComponent(selectedCandidate.id) + "/evaluate-runs",
        {
          method: "POST",
          body: {
            baseline_run_id: evidence.baseline.id,
            candidate_target_run_id: evidence.target.id,
            regression_run_ids: evidence.regressions.map((item) => item.run!.id),
          },
        },
      );
      await refreshWorkspace(projectId, undefined, evaluated.id);
      setView("candidates");
      const result = evaluated.latest_evaluation;
      setNotice({ kind: result?.outcome === "passed" ? "success" : "info", text: result ? "Saved-run gate: " + nice(result.outcome) + ". " + result.reason : "Candidate evaluation was saved." });
    } catch (error) {
      setNotice({ kind: "error", text: error instanceof Error ? error.message : "Could not evaluate candidate." });
    } finally {
      setBusy("");
    }
  }

  async function onCreateCandidate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!projectId || !candidateTargetScenarioId) {
      setNotice({ kind: "info", text: "Select a target scenario before creating a candidate." });
      return;
    }
    setBusy("create-candidate");
    setNotice(null);
    try {
      const created = await api<Candidate>("projects/" + encodeURIComponent(projectId) + "/candidates", {
        method: "POST",
        body: { scenario_id: candidateTargetScenarioId, hypothesis: hypothesis.trim(), proposed_change: proposedChange.trim() },
      });
      await refreshWorkspace(projectId, undefined, created.id);
      setHypothesis("");
      setProposedChange("");
      setView("candidates");
      setNotice({ kind: "success", text: "Candidate proposal saved. Run a failing baseline before testing it." });
    } catch (error) {
      setNotice({ kind: "error", text: error instanceof Error ? error.message : "Could not save candidate." });
    } finally {
      setBusy("");
    }
  }

  async function reviewCandidate(decision: "accept" | "reject") {
    if (!projectId || !selectedCandidate) return;
    const evaluation = selectedCandidate.latest_evaluation;
    if (!evaluation) {
      setNotice({ kind: "error", text: "Evaluate the candidate before recording a review decision." });
      return;
    }
    if (decision === "accept" && (evaluation.outcome !== "passed" || evaluation.evidence_mode !== "live")) {
      setNotice({ kind: "error", text: "Only a passing evaluation based on live evidence can be approved." });
      return;
    }
    setBusy("review-" + decision);
    setNotice(null);
    try {
      const result = await api<Candidate>("candidates/" + encodeURIComponent(selectedCandidate.id) + "/review", {
        method: "POST",
        body: { decision, reviewer: reviewer.trim() || "Local reviewer", note: reviewNote.trim() || null },
      });
      await refreshWorkspace(projectId, undefined, result.id);
      setNotice({
        kind: decision === "accept" ? "success" : "info",
        text: decision === "accept" ? "Candidate approved for release review. Pixi has not deployed or changed production." : "Candidate rejected. No production agent was changed.",
      });
    } catch (error) {
      setNotice({ kind: "error", text: error instanceof Error ? error.message : "Could not save review." });
    } finally {
      setBusy("");
    }
  }

  async function exportProject() {
    if (!projectId) return;
    setBusy("export");
    setNotice(null);
    try {
      const response = await fetch("/api/pixi/projects/" + encodeURIComponent(projectId) + "/export", { cache: "no-store" });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({})) as { detail?: string };
        throw new Error(payload.detail || "Export failed (HTTP " + response.status + ").");
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "pixi-project-" + projectId + ".json";
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      setNotice({ kind: "success", text: "Project evidence backup downloaded. Keep the JSON file somewhere safe." });
    } catch (error) {
      setNotice({ kind: "error", text: error instanceof Error ? error.message : "Export failed." });
    } finally {
      setBusy("");
    }
  }

  async function importProject(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setBusy("import");
    setLoading(true);
    setNotice(null);
    try {
      if (file.size > 20_000_000) throw new Error("Backup is larger than the local 20 MB import limit.");
      const parsed: unknown = JSON.parse(await file.text());
      const restored = await api<Project>("projects/import", { method: "POST", body: parsed });
      await refreshProjectList(restored.id);
      setView("overview");
      setNotice({ kind: "success", text: "Backup restored as “" + restored.name + "”. The source project was not changed." });
    } catch (error) {
      setNotice({ kind: "error", text: error instanceof Error ? error.message : "Could not restore this backup." });
    } finally {
      setBusy("");
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  const selectedEvidence = selectedCandidate ? evidenceForCandidate(selectedCandidate) : null;
  const canAccept = Boolean(
    selectedCandidate && selectedCandidate.latest_evaluation &&
    selectedCandidate.latest_evaluation.outcome === "passed" &&
    selectedCandidate.latest_evaluation.evidence_mode === "live",
  );
  const gateReady = Boolean(
    selectedEvidence && selectedEvidence.baseline && selectedEvidence.baseline.status === "failed" &&
    selectedEvidence.target && selectedEvidence.regressions.length > 0 &&
    selectedEvidence.missingRegressions.length === 0,
  );

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark">P</div><div><div className="brand-name">pixi</div><div className="brand-sub">VOICE RELIABILITY</div></div></div>
        <div>
          <div className="nav-label">Workspace</div>
          <nav className="nav-list" aria-label="Main navigation">
            {NAV.map((item) => {
              const Icon = item.icon;
              const active = view === item.id;
              const count = item.id === "scenarios" ? scenarios.length : item.id === "runs" ? runs.length : item.id === "candidates" ? candidates.length : null;
              return (
                <button className={"nav-item " + (active ? "active" : "")} key={item.id} type="button" onClick={() => setView(item.id)} aria-current={active ? "page" : undefined}>
                  <span className="nav-icon"><Icon size={16} strokeWidth={1.8} /></span><span>{item.label}</span>
                  {count !== null ? <span className="nav-count">{count}</span> : null}
                </button>
              );
            })}
          </nav>
        </div>
        <div className="sidebar-bottom">
          <div className="local-state">
            <strong><span className={"dot " + (connected ? "" : "amber")} />{connected ? "API connected" : "API not connected"}</strong>
            <p>{connected ? "Local workspace · evidence saved to your configured database." : "Start FastAPI and refresh the page to load projects."}</p>
          </div>
          <div className="sidebar-foot">EARLY ACCESS · LOCAL-FIRST</div>
        </div>
      </aside>

      <div className="main-wrap">
        <header className="topbar">
          <div className="topbar-left">
            <div className="breadcrumb"><span>Pixi</span><span> / </span><strong>{page.title}</strong></div><ChevronDown size={13} color="var(--subtle)" />
            <select aria-label="Active project" className="project-select" value={projectId} onChange={(event) => { setLoading(true); setProjectId(event.target.value); setSelectedRunId(""); }} disabled={!projects.length}>
              {!projects.length ? <option value="">No projects yet</option> : null}
              {projects.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </div>
          <div className="topbar-actions">
            <button className="btn secondary" type="button" onClick={() => setShowProjectModal(true)}><Plus size={14} /> New project</button>
            <button className="btn secondary" type="button" onClick={() => void exportProject()} disabled={!projectId || busy === "export" || busy === "import"}>
              {busy === "export" ? <LoaderCircle size={14} /> : <Download size={14} />} Backup
            </button>
            <input ref={fileInputRef} hidden type="file" accept=".json,application/json" onChange={(event) => void importProject(event)} />
            <button className="btn ghost" type="button" onClick={() => fileInputRef.current?.click()} disabled={busy === "import"}><Upload size={14} /> Restore</button>
          </div>
        </header>

        <main className="content">
          <div className="page-header">
            <div><div className="eyebrow">{page.eyebrow}</div><h1>{page.title}</h1><p className="subtitle">{page.description}</p></div>
            <div className="inline">
              {project ? <span className="pill"><Database size={11} /> {project.name}</span> : null}
              <span className="pill simulated">LOCAL DEVELOPMENT</span>
            </div>
          </div>

          {notice ? <NoticeBar notice={notice} onDismiss={() => setNotice(null)} /> : null}

          {!projects.length && !loading ? (
            <section className="panel" style={{ marginBottom: 17 }}>
              <EmptyState icon={<Sparkles size={19} />} title="Your workspace starts here" description="Create a Pixi project to save scenarios, run evidence, candidate hypotheses, and review decisions." action={<button className="btn" type="button" onClick={() => setShowProjectModal(true)}><Plus size={14} /> Create first project</button>} />
            </section>
          ) : null}

          {view === "overview" ? (
            <div className="grid">
              <div className="grid metrics">
                <MetricCard label="Scenarios" value={scenarios.length} foot="Saved test cases" />
                <MetricCard label="Total runs" value={runs.length} foot="Saved evidence records" tone="green" />
                <MetricCard label="Failed runs" value={failedCount} foot="Cases needing attention" tone={failedCount ? "red" : "green"} />
                <MetricCard label="Live runs" value={liveCount} foot="External bridge evidence" tone="amber" />
              </div>
              <div className="callout"><div className="callout-icon"><ShieldCheck size={17} /></div><div style={{ flex: 1 }}><h3>Evidence first. No automatic production mutations.</h3><p>Pixi stores scenario snapshots, observations, assertion outcomes, candidate/version provenance, and review history. A candidate requires a passing live-evidence gate and a human decision; Pixi does not deploy it.</p></div></div>
              <div className="grid two-col">
                <section className="panel">
                  <div className="section-head"><div><h2>Recent evidence</h2><p>The newest saved runs in this project.</p></div><button className="btn ghost small" type="button" onClick={() => setView("runs")}>All runs <ArrowDownToLine size={12} /></button></div>
                  {!sortedRuns.length ? <EmptyState icon={<Activity size={18} />} title="No runs saved" description="Start with a baseline against your configured bridge or use the clearly simulated fixture sandbox." action={<button className="btn secondary" type="button" onClick={() => setView("runs")}>Open run history</button>} /> : (
                    <div className="list">{sortedRuns.slice(0, 5).map((run) => (
                      <button className="list-item" key={run.id} type="button" onClick={() => { setSelectedRunId(run.id); setView("runs"); }}>
                        <div className="list-item-main"><div className="list-title">{run.scenario_snapshot.name}</div><div className="list-meta">{formatDate(run.started_at)} · {run.agent_version || "version missing"}</div></div>
                        <div className="list-trailing"><StatusPill value={run.status} /><StatusPill value={run.evidence_mode} /></div>
                      </button>
                    ))}</div>
                  )}
                </section>
                <section className="panel">
                  <div className="section-head"><div><h2>Recommended next steps</h2><p>Build a trustworthy evaluation loop from the bottom up.</p></div><Sparkles size={16} color="var(--accent)" /></div>
                  <div className="list">
                    <button className="list-item" type="button" onClick={() => setView("scenarios")}><div className="callout-icon"><Layers3 size={16} /></div><div className="list-item-main"><div className="list-title">01 · Create target and regression scenarios</div><div className="list-meta">Use explicit checks and mark safety-critical assertions.</div></div></button>
                    <button className="list-item" type="button" onClick={() => setView("setup")}><div className="callout-icon"><AudioLines size={16} /></div><div className="list-item-main"><div className="list-title">02 · Connect your voice-agent runtime</div><div className="list-meta">Implement the documented bridge with real observed traces and immutable build IDs.</div></div></button>
                    <button className="list-item" type="button" onClick={() => setView("candidates")}><div className="callout-icon"><GitBranch size={16} /></div><div className="list-item-main"><div className="list-title">03 · Test a proposed fix</div><div className="list-meta">Compare a failed baseline to one candidate version and the full saved regression suite.</div></div></button>
                  </div>
                </section>
              </div>
            </div>
          ) : null}

          {view === "scenarios" ? (
            <div className="grid two-col">
              <section className="panel">
                <div className="section-head"><div><h2>New scenario</h2><p>One or more user turns plus explicit assertion JSON.</p></div><span className="pill">SCHEMA VALIDATED</span></div>
                <form onSubmit={(event) => void onCreateScenario(event)}>
                  <div className="field"><label htmlFor="scenario-name">Scenario name</label><input id="scenario-name" value={scenarioName} onChange={(event) => setScenarioName(event.target.value)} maxLength={120} required /></div>
                  <div className="field"><label htmlFor="scenario-turns">User turns · one per line</label><textarea id="scenario-turns" value={scenarioTurns} onChange={(event) => setScenarioTurns(event.target.value)} required rows={4} placeholder={"How much is the basic plan?\nCan I cancel at any time?"} /><p className="hint">The bridge receives turns and assertion definitions. Multi-turn audio orchestration remains runtime-specific.</p></div>
                  <div className="field"><label htmlFor="scenario-assertions">Assertions · JSON array</label><textarea className="mono-area" id="scenario-assertions" value={assertionsJson} onChange={(event) => setAssertionsJson(event.target.value)} rows={12} required spellCheck={false} /><p className="hint">Kinds: <code>contains</code>, <code>not_contains</code>, <code>max_latency_ms</code>, <code>tool_called</code>, <code>tool_not_called</code>. Use <code>critical: true</code> for checks that must never regress.</p></div>
                  <div className="form-actions"><button className="btn" disabled={!projectId || busy !== ""} type="submit">{busy === "create-scenario" ? <LoaderCircle size={14} /> : <Plus size={14} />} Save scenario</button></div>
                </form>
              </section>
              <section className="panel">
                <div className="section-head"><div><h2>Project scenarios</h2><p>{scenarios.length} saved · all non-target scenarios are required by the current candidate gate.</p></div><StatusPill value="regression suite" /></div>
                {!scenarios.length ? <EmptyState icon={<Layers3 size={18} />} title="No scenarios yet" description="Create a target and at least one separate regression scenario." /> : (
                  <div className="list">{scenarios.map((scenario) => {
                    const count = runs.filter((run) => run.scenario_id === scenario.id).length;
                    const criticalCount = scenario.definition.assertions.filter((item) => item.critical).length;
                    return (
                      <button className={"list-item " + (selectedScenarioId === scenario.id ? "selected" : "")} key={scenario.id} type="button" onClick={() => setSelectedScenarioId(scenario.id)}>
                        <div className="callout-icon"><Layers3 size={15} /></div>
                        <div className="list-item-main"><div className="list-title">{scenario.name}</div><div className="list-meta">{scenario.definition.turns.length} turn(s) · {scenario.definition.assertions.length} assertion(s) · {count} run(s)</div><div className="list-meta">{scenario.definition.turns[0]}</div></div>
                        <div className="list-trailing">{criticalCount ? <span className="pill failed">{criticalCount} critical</span> : null}{selectedScenarioId === scenario.id ? <CheckCircle2 size={15} color="var(--accent)" /> : null}</div>
                      </button>
                    );
                  })}</div>
                )}
                <div className="rule" />
                <div className="field"><label htmlFor="scenario-picker">Scenario used by run controls</label><select id="scenario-picker" value={selectedScenarioId} onChange={(event) => setSelectedScenarioId(event.target.value)} disabled={!scenarios.length}>{scenarios.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div>
                {selectedScenario ? <div className="evidence-block"><h3>Selected target definition</h3><div className="list-meta mono wrap">{selectedScenario.definition.turns.join(" → ")}</div></div> : null}
              </section>
            </div>
          ) : null}

          {view === "runs" ? (
            <div className="grid">
              <section className="panel">
                <div className="section-head"><div><h2>Execute a scenario</h2><p>Live calls use the server-configured bridge. Fixture runs are simulated and never count as live evidence.</p></div><StatusPill value={selectedScenario ? selectedScenario.name : "no scenario selected"} /></div>
                <div className="form-grid">
                  <div className="field"><label htmlFor="run-scenario">Scenario</label><select id="run-scenario" value={selectedScenarioId} onChange={(event) => setSelectedScenarioId(event.target.value)} disabled={!scenarios.length}>{scenarios.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div>
                  <div className="field"><label htmlFor="run-candidate">Candidate variant (optional)</label><select id="run-candidate" value={selectedCandidateId} onChange={(event) => setSelectedCandidateId(event.target.value)}><option value="">Baseline / no candidate</option>{sortedCandidates.map((item) => <option value={item.id} key={item.id}>{item.hypothesis.slice(0, 66)}</option>)}</select></div>
                </div>
                <div className="grid three-col">
                  <div className="evidence-block"><div className="row"><span className="pill baseline">BASELINE</span><AudioLines size={13} color="var(--accent)" /></div><h3 style={{ marginTop: 12 }}>Run actual agent</h3><p className="hint">Establish current behavior and version before a candidate change.</p><button className="btn full" type="button" disabled={!selectedScenario || busy !== ""} onClick={() => void runScenario(selectedScenarioId, "baseline")}><Zap size={14} /> Run baseline</button></div>
                  <div className="evidence-block"><div className="row"><span className="pill candidate">CANDIDATE</span><GitBranch size={13} color="#c4b5fd" /></div><h3 style={{ marginTop: 12 }}>Run selected variant</h3><p className="hint">The bridge must execute this candidate in isolated staging, not production.</p><button className="btn secondary full" type="button" disabled={!selectedScenario || !selectedCandidate || busy !== ""} onClick={() => void runScenario(selectedScenarioId, "candidate", selectedCandidateId)}><ArrowLeftRight size={14} /> Run candidate</button></div>
                  <div className="evidence-block"><div className="row"><span className="pill simulated">SIMULATED</span><FlaskConical size={13} color="var(--amber)" /></div><h3 style={{ marginTop: 12 }}>Fixture sandbox</h3><p className="hint">Test assertion policy with supplied output; this is not live-agent evidence.</p><button className="btn ghost full" type="button" disabled={!selectedScenario || busy !== ""} onClick={() => void runScenario(selectedScenarioId, "fixture")}><FlaskConical size={14} /> Run simulated fixture</button></div>
                </div>
                {busy.startsWith("run-") || busy === "fixture-run" ? <div className="notice info" style={{ marginTop: 14, marginBottom: 0 }}><LoaderCircle size={14} /> Request in progress. The backend saves each run before history refresh.</div> : null}
                <div className="rule" />
                <details>
                  <summary style={{ cursor: "pointer", color: "var(--muted)", fontSize: 11, fontWeight: 700 }}>Edit simulated fixture output</summary>
                  <div className="field"><label htmlFor="fixture-transcript">Fixture transcript</label><textarea id="fixture-transcript" value={fixtureTranscript} onChange={(event) => setFixtureTranscript(event.target.value)} rows={3} /></div>
                  <div className="field"><label htmlFor="fixture-latency">Latency in milliseconds</label><input id="fixture-latency" value={fixtureLatency} onChange={(event) => setFixtureLatency(event.target.value)} inputMode="decimal" /></div>
                </details>
              </section>
              <div className="grid two-col">
                <section className="panel">
                  <div className="section-head"><div><h2>Saved runs</h2><p>{runs.length} most recent records from this project.</p></div><button className="btn ghost small" type="button" onClick={() => { if (projectId) void refreshWorkspace(projectId); }} disabled={!projectId || busy !== ""}><RefreshCw size={13} /> Refresh</button></div>
                  {!sortedRuns.length ? <EmptyState icon={<Activity size={18} />} title="No evidence available" description="Run a baseline, candidate variant, or fixture to create a saved record." /> : (
                    <div className="list">{sortedRuns.map((run) => (
                      <button className={"list-item " + (selectedRunId === run.id ? "selected" : "")} key={run.id} type="button" onClick={() => setSelectedRunId(run.id)}>
                        <div className="list-item-main"><div className="list-title">{run.scenario_snapshot.name}</div><div className="list-meta">{formatDate(run.started_at)} · {run.agent_version || "version missing"}</div><div className="list-meta mono">{run.id.slice(0, 8)} · {run.adapter_name}</div></div>
                        <div className="list-trailing"><StatusPill value={run.status} /><StatusPill value={run.evidence_mode} /><StatusPill value={run.variant} /></div>
                      </button>
                    ))}</div>
                  )}
                </section>
                <section className="panel"><div className="section-head"><div><h2>Run evidence</h2><p>Inspection view of the selected saved run.</p></div>{selectedRun ? <StatusPill value={selectedRun.status} /> : null}</div>{selectedRun ? <RunDetail run={selectedRun} /> : <EmptyState icon={<FileJson size={18} />} title="Select a run" description="Saved transcripts, latency, tools, and assertions appear here." />}</section>
              </div>
            </div>
          ) : null}

          {view === "candidates" ? (
            <div className="grid two-col">
              <div className="grid">
                <section className="panel">
                  <div className="section-head"><div><h2>Propose a candidate</h2><p>Write down why this change should fix the target failure before testing.</p></div><span className="pill candidate">HYPOTHESIS</span></div>
                  <form onSubmit={(event) => void onCreateCandidate(event)}>
                    <div className="field"><label htmlFor="candidate-target-scenario">Target scenario</label><select id="candidate-target-scenario" value={candidateTargetScenarioId} onChange={(event) => setCandidateTargetScenarioId(event.target.value)} required disabled={!scenarios.length}>{scenarios.map((scenario) => <option key={scenario.id} value={scenario.id}>{scenario.name}</option>)}</select></div>
                    <div className="field"><label htmlFor="candidate-hypothesis">Hypothesis</label><textarea id="candidate-hypothesis" value={hypothesis} onChange={(event) => setHypothesis(event.target.value)} maxLength={2000} required placeholder="A direct answer before the explanation should reduce failed pricing responses." rows={3} /></div>
                    <div className="field"><label htmlFor="candidate-change">Proposed change</label><textarea id="candidate-change" value={proposedChange} onChange={(event) => setProposedChange(event.target.value)} maxLength={10000} required placeholder="Describe a small, reversible change for the staging agent configuration." rows={4} /></div>
                    <div className="notice info"><LockKeyhole size={14} /><span>Pixi records a proposal; it does not execute arbitrary code or mutate production. Your bridge must safely stage the candidate and return the actual immutable build/configuration ID.</span></div>
                    <div className="form-actions"><button className="btn" type="submit" disabled={!projectId || !scenarios.length || busy !== ""}><Plus size={14} /> Save candidate</button></div>
                  </form>
                </section>
                <section className="panel">
                  <div className="section-head"><div><h2>Candidate queue</h2><p>{candidates.length} saved hypotheses.</p></div><span className="section-tag">No auto-deploy</span></div>
                  {!sortedCandidates.length ? <EmptyState icon={<GitBranch size={18} />} title="No candidates yet" description="Save a hypothesis, then run a failing baseline and the candidate against the full regression suite." /> : (
                    <div className="list">{sortedCandidates.map((candidate) => (
                      <button className={"list-item " + (selectedCandidateId === candidate.id ? "selected" : "")} key={candidate.id} type="button" onClick={() => setSelectedCandidateId(candidate.id)}>
                        <div className="callout-icon"><GitBranch size={15} /></div>
                        <div className="list-item-main"><div className="list-title">{candidate.hypothesis}</div><div className="list-meta">{scenarios.find((item) => item.id === candidate.scenario_id)?.name || "Unknown target"} · {formatDate(candidate.created_at)}</div><div className="list-meta">{candidate.proposed_change}</div></div>
                        <div className="list-trailing"><StatusPill value={candidate.status} />{candidate.latest_evaluation ? <StatusPill value={candidate.latest_evaluation.outcome} /> : <span className="pill">Not evaluated</span>}</div>
                      </button>
                    ))}</div>
                  )}
                </section>
              </div>
              <div className="grid">
                <section className="panel">
                  <div className="section-head"><div><h2>Candidate experiment</h2><p>Run the saved variant and evaluate saved evidence.</p></div><Sparkles size={16} color="var(--accent)" /></div>
                  {!selectedCandidate ? <EmptyState icon={<GitBranch size={18} />} title="Select a candidate" description="Candidate baseline and regression evidence will appear here." /> : (
                    <>
                      <div className="evidence-block"><div className="row" style={{ justifyContent: "space-between" }}><h3>{selectedCandidate.hypothesis}</h3><StatusPill value={selectedCandidate.status} /></div><p className="transcript" style={{ marginTop: 10 }}>{selectedCandidate.proposed_change}</p><p className="hint">Target: {scenarios.find((item) => item.id === selectedCandidate.scenario_id)?.name || selectedCandidate.scenario_id}</p></div>
                      <div className="field"><label htmlFor="candidate-run-scenario">Scenario to run for this candidate</label><select id="candidate-run-scenario" value={selectedScenarioId} onChange={(event) => setSelectedScenarioId(event.target.value)} disabled={!scenarios.length}>{scenarios.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select></div>
                      <button className="btn secondary full" type="button" disabled={!selectedScenario || busy !== ""} onClick={() => void runScenario(selectedScenarioId, "candidate", selectedCandidate.id)}><ArrowLeftRight size={14} /> Run selected scenario on candidate</button>
                      <button className="btn full" style={{ marginTop: 9 }} type="button" disabled={busy !== "" || !scenarios.length} onClick={() => void runCandidateSuite(selectedCandidate)}>{busy === "candidate-suite" ? <LoaderCircle size={14} /> : <Zap size={14} />} Run candidate across all scenarios</button>
                      {busy === "candidate-suite" ? <div style={{ marginTop: 12 }}><div className="row" style={{ justifyContent: "space-between", marginBottom: 7 }}><span className="hint">Running staged candidate</span><span className="mono">{suiteProgress}</span></div><div className="progress-line"><span style={{ width: Math.max(6, (Number(suiteProgress.split(" / ")[0]) || 1) / Math.max(1, scenarios.length) * 100) + "%" }} /></div></div> : null}
                      <p className="hint">Each scenario produces a separate saved run. The bridge must return the same candidate version for the target and every regression scenario.</p>
                      <div className="rule" />
                      <div className="section-head"><div><h2>Evidence gate</h2><p>Derived from saved runs, not caller-submitted pass/fail booleans.</p></div><StatusPill value={gateReady ? "evidence ready" : "evidence incomplete"} /></div>
                      {selectedEvidence ? (
                        <div className="list">
                          <div className="list-item"><div className="list-item-main"><div className="list-title">Baseline · target must fail</div><div className="list-meta">{selectedEvidence.baseline ? nice(selectedEvidence.baseline.status) + " · " + (selectedEvidence.baseline.agent_version || "version missing") : "No baseline run"}</div></div>{selectedEvidence.baseline ? <StatusPill value={selectedEvidence.baseline.status} /> : <span className="pill">Missing</span>}</div>
                          <div className="list-item"><div className="list-item-main"><div className="list-title">Candidate · target scenario</div><div className="list-meta">{selectedEvidence.target ? nice(selectedEvidence.target.status) + " · " + (selectedEvidence.target.agent_version || "version missing") : "No candidate target run"}</div></div>{selectedEvidence.target ? <StatusPill value={selectedEvidence.target.status} /> : <span className="pill">Missing</span>}</div>
                          {selectedEvidence.regressions.map(({ scenario, run }) => <div className="list-item" key={scenario.id}><div className="list-item-main"><div className="list-title">Regression · {scenario.name}</div><div className="list-meta">{run ? nice(run.status) + " · " + (run.agent_version || "version missing") : "Candidate suite run required"}</div></div>{run ? <StatusPill value={run.status} /> : <span className="pill">Missing</span>}</div>)}
                        </div>
                      ) : null}
                      <button className="btn full" style={{ marginTop: 13 }} type="button" disabled={busy !== "" || !gateReady} onClick={() => void evaluateSelectedCandidate()}>{busy === "evaluate-candidate" ? <LoaderCircle size={14} /> : <ShieldCheck size={14} />} Evaluate saved live evidence</button>
                      {!gateReady ? <p className="hint">The gate stays locked until the latest live baseline fails, a candidate target run is saved, and every other project scenario has a candidate run.</p> : null}
                      {selectedCandidate.latest_evaluation ? (
                        <div className="evidence-block" style={{ marginTop: 14 }}>
                          <div className="row" style={{ justifyContent: "space-between" }}><h3>Latest evaluation</h3><StatusPill value={selectedCandidate.latest_evaluation.outcome} /></div>
                          <p>{selectedCandidate.latest_evaluation.reason}</p>
                          <div className="detail-grid"><div className="detail-cell"><span>Target passed</span><strong>{selectedCandidate.latest_evaluation.target_passed === null ? "Unknown" : selectedCandidate.latest_evaluation.target_passed ? "Yes" : "No"}</strong></div><div className="detail-cell"><span>Regressions</span><strong>{selectedCandidate.latest_evaluation.regression_count}</strong></div><div className="detail-cell"><span>Evidence</span><strong>{nice(selectedCandidate.latest_evaluation.evidence_mode)}</strong></div></div>
                          {selectedCandidate.latest_evaluation.critical_regressions.length ? <p style={{ color: "var(--red)" }}>Critical regressions: {selectedCandidate.latest_evaluation.critical_regressions.join(", ")}</p> : null}
                          {selectedCandidate.latest_evaluation.review_decision ? <p className="hint">Review: {nice(selectedCandidate.latest_evaluation.review_decision)} · {selectedCandidate.latest_evaluation.reviewer || "reviewer unknown"}</p> : null}
                        </div>
                      ) : null}
                      <div className="rule" />
                      <h3>Human review</h3>
                      <div className="field"><label htmlFor="reviewer">Reviewer</label><input id="reviewer" value={reviewer} onChange={(event) => setReviewer(event.target.value)} maxLength={120} /></div>
                      <div className="field"><label htmlFor="review-note">Review note</label><textarea id="review-note" rows={2} value={reviewNote} onChange={(event) => setReviewNote(event.target.value)} maxLength={2000} placeholder="Why accept or reject this candidate?" /></div>
                      <div className="grid two-col"><button className="btn success" type="button" disabled={busy !== "" || !canAccept} onClick={() => void reviewCandidate("accept")}><BadgeCheck size={14} /> Approve for release</button><button className="btn danger" type="button" disabled={busy !== "" || !selectedCandidate.latest_evaluation} onClick={() => void reviewCandidate("reject")}><XCircle size={14} /> Reject</button></div>
                      <p className="hint">Approval records a human decision only. Pixi does not deploy or hot-patch the production agent.</p>
                    </>
                  )}
                </section>
              </div>
            </div>
          ) : null}

          {view === "setup" ? (
            <div className="grid two-col">
              <div className="grid">
                <section className="panel">
                  <div className="section-head"><div><h2>Run locally</h2><p>Two processes: the FastAPI backend and Next.js app.</p></div><Code2 size={16} color="var(--accent)" /></div>
                  <div className="evidence-block"><h3>Terminal 1 · backend</h3><pre className="transcript">{"cd backend\npython -m venv .venv\nsource .venv/bin/activate\npip install -e \".[dev]\"\n# Optional: load root .env for PostgreSQL / bridge config\n# set -a && source ../.env && set +a\nexport APP_ENV=development\nalembic upgrade head\nuvicorn app.main:app --reload --port 8000"}</pre><p className="hint">The default database is SQLite at <code>backend/pixi.db</code>. Root <code>.env</code> is not loaded automatically by FastAPI; source it from <code>backend/</code> if you choose PostgreSQL or configure the LiveKit bridge.</p></div>
                  <div className="evidence-block" style={{ marginTop: 12 }}><h3>Terminal 2 · web</h3><pre className="transcript">{"cd web\nnpm install\nnpm run dev"}</pre><p className="hint">Open <code>http://localhost:3000</code>. The same-origin Next.js route handler forwards to <code>127.0.0.1:8000/api/v1</code>.</p></div>
                  <div className="notice info" style={{ marginTop: 12 }}><LockKeyhole size={14} /><span>The backend and Next.js proxy intentionally refuse production API access until authentication and project authorization exist. Do not expose this development setup on a public network.</span></div>
                </section>
                <section className="panel">
                  <div className="section-head"><div><h2>Stack</h2><p>Typed UI over the existing Python evaluation service.</p></div><Layers3 size={16} color="var(--accent)" /></div>
                  <div className="list">
                    <div className="list-item"><div className="callout-icon"><Code2 size={15} /></div><div className="list-item-main"><div className="list-title">Next.js App Router + React + TypeScript</div><div className="list-meta">Typed API contracts, reusable screens, same-origin server proxy, build and lint checks.</div></div></div>
                    <div className="list-item"><div className="callout-icon"><Database size={15} /></div><div className="list-item-main"><div className="list-title">FastAPI + SQLAlchemy + Alembic</div><div className="list-meta">Scenario execution, observations/assertions, run provenance and project backups.</div></div></div>
                    <div className="list-item"><div className="callout-icon"><ShieldCheck size={15} /></div><div className="list-item-main"><div className="list-title">Evidence-based candidate gate</div><div className="list-meta">Baseline precondition, candidate version checks, full project regression coverage, and human review.</div></div></div>
                  </div>
                </section>
              </div>
              <div className="grid">
                <section className="panel">
                  <div className="section-head"><div><h2>Configure the voice-agent bridge</h2><p>Values live on the backend server, never in the browser.</p></div><AudioLines size={16} color="var(--accent)" /></div>
                  <div className="evidence-block"><h3>.env (local only)</h3><pre className="transcript">{"APP_ENV=development\nDATABASE_URL=postgresql+psycopg://pixi:pixi@localhost:5432/pixi\n\nPIXI_AGENT_ENDPOINT=https://your-staging-bridge.example/evaluate\nPIXI_AGENT_API_KEY=your-local-secret\nPIXI_AGENT_TIMEOUT_SECONDS=15"}</pre></div>
                  <p className="hint">Never commit a real key. HTTPS is required except loopback HTTP during local development. Redirects are not followed; bridge responses must satisfy the versioned schema.</p>
                  <a className="btn secondary" href="https://github.com/devxMani/Pixi/blob/main/docs/AGENT_BRIDGE.md" target="_blank" rel="noreferrer"><ExternalLink size={13} /> Read bridge protocol</a>
                  <div className="rule" /><h3>Required response provenance</h3>
                  <div className="list">
                    <div className="list-item"><div className="callout-icon"><CheckCircle2 size={15} /></div><div className="list-item-main"><div className="list-title">Actual observed transcript and trace fields</div><div className="list-meta">The bridge must run your agent, not echo the prompt or invent tool calls.</div></div></div>
                    <div className="list-item"><div className="callout-icon"><GitBranch size={15} /></div><div className="list-item-main"><div className="list-title">Immutable agent version</div><div className="list-meta">Candidate target and regressions must report the same candidate build/config version.</div></div></div>
                    <div className="list-item"><div className="callout-icon"><LockKeyhole size={15} /></div><div className="list-item-main"><div className="list-title">Isolated, non-production candidate execution</div><div className="list-meta">Pixi does not stage code automatically; the bridge owns the runtime-specific safe mechanism.</div></div></div>
                  </div>
                </section>
                <section className="panel">
                  <div className="section-head"><div><h2>API status</h2><p>Connection to your local development backend.</p></div><span className={"pill " + (connected ? "live" : "inconclusive")}>{connected ? "Connected" : "Unavailable"}</span></div>
                  <div className="detail-grid"><div className="detail-cell"><span>Projects</span><strong>{projects.length}</strong></div><div className="detail-cell"><span>Scenarios</span><strong>{scenarios.length}</strong></div><div className="detail-cell"><span>Runs loaded</span><strong>{runs.length}</strong></div></div>
                  <button className="btn secondary full" style={{ marginTop: 12 }} type="button" disabled={loading || busy !== ""} onClick={async () => {
                    setLoading(true);
                    try {
                      const list = await refreshProjectList();
                      if (projectId && list.some((item) => item.id === projectId)) await refreshWorkspace(projectId);
                      setNotice({ kind: "success", text: "Workspace refreshed from the API." });
                    } catch (error) {
                      setNotice({ kind: "error", text: error instanceof Error ? error.message : "Refresh failed." });
                    } finally { setLoading(false); }
                  }}><RefreshCw size={14} /> Refresh connection</button>
                </section>
              </div>
            </div>
          ) : null}

          {loading ? <div className="hint" style={{ marginTop: 17 }}><LoaderCircle size={13} /> Syncing saved project state…</div> : null}
          <footer style={{ marginTop: 23, display: "flex", justifyContent: "space-between", gap: 14, color: "var(--subtle)", fontSize: 10 }}><span>Pixi · evidence before confidence</span><span>Development-only API · no automatic production mutation</span></footer>
        </main>
      </div>

      <nav className="mobile-nav" aria-label="Mobile navigation">
        {NAV.map((item) => {
          const Icon = item.icon;
          return <button className={"nav-item " + (view === item.id ? "active" : "")} key={item.id} type="button" onClick={() => setView(item.id)}><span className="nav-icon"><Icon size={17} /></span><span>{item.label === "Run history" ? "Runs" : item.label === "Setup & docs" ? "Setup" : item.label}</span></button>;
        })}
      </nav>

      {showProjectModal ? (
        <div className="modal-scrim" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setShowProjectModal(false); }}>
          <section className="modal" role="dialog" aria-modal="true" aria-labelledby="new-project-title">
            <div className="section-head"><div><div className="eyebrow">New workspace</div><h2 id="new-project-title" style={{ marginTop: 4, fontSize: 18 }}>Create a Pixi project</h2><p>Projects keep scenarios, runs, candidates, and evidence together.</p></div><button className="btn ghost small" type="button" aria-label="Close" onClick={() => setShowProjectModal(false)}><X size={14} /></button></div>
            <form onSubmit={(event) => void onCreateProject(event)}>
              <div className="field"><label htmlFor="project-name">Project name</label><input id="project-name" value={projectName} onChange={(event) => setProjectName(event.target.value)} required maxLength={120} placeholder="Customer support voice agent" autoFocus /></div>
              <div className="form-actions"><button className="btn secondary" type="button" onClick={() => setShowProjectModal(false)}>Cancel</button><button className="btn" type="submit" disabled={!projectName.trim() || busy === "create-project"}>{busy === "create-project" ? <LoaderCircle size={14} /> : <Plus size={14} />} Create project</button></div>
            </form>
          </section>
        </div>
      ) : null}
    </div>
  );
}

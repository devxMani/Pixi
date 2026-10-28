import type {
  ApiErrorPayload,
  Candidate,
  Project,
  RunRecord,
  ScenarioRecord,
} from "@/lib/types";

type JsonRequestInit = Omit<RequestInit, "body"> & { body?: unknown };

export async function api<T>(
  path: string,
  options: JsonRequestInit = {},
): Promise<T> {
  const normalized = path.replace(/^\/+/, "");
  const headers = new Headers(options.headers);
  let body: BodyInit | undefined;

  if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
    body =
      typeof options.body === "string"
        ? options.body
        : JSON.stringify(options.body);
  }

  headers.set("Accept", "application/json");

  let response: Response;
  try {
    response = await fetch(`/api/pixi/${normalized}`, {
      ...options,
      headers,
      body,
      cache: "no-store",
    });
  } catch {
    throw new Error(
      "Could not reach the Pixi web API. Start the FastAPI backend on port 8000.",
    );
  }

  const contentType = response.headers.get("content-type") ?? "";
  const payload: unknown = contentType.includes("application/json")
    ? await response.json().catch(() => ({}))
    : await response.text().catch(() => "");

  if (!response.ok) {
    const errorPayload = payload as ApiErrorPayload;
    const message =
      typeof errorPayload?.detail === "string"
        ? errorPayload.detail
        : typeof errorPayload?.message === "string"
          ? errorPayload.message
          : typeof payload === "string" && payload
            ? payload
            : `Pixi API request failed (HTTP ${response.status}).`;
    throw new Error(message);
  }

  return payload as T;
}

export async function getProjects(): Promise<Project[]> {
  return api<Project[]>("projects?limit=200");
}

export async function getProjectWorkspace(projectId: string): Promise<{
  scenarios: ScenarioRecord[];
  runs: RunRecord[];
  candidates: Candidate[];
}> {
  const encoded = encodeURIComponent(projectId);
  const [scenarios, runs, candidates] = await Promise.all([
    api<ScenarioRecord[]>(`projects/${encoded}/scenarios?limit=200`),
    api<RunRecord[]>(`projects/${encoded}/runs?limit=100`),
    api<Candidate[]>(`projects/${encoded}/candidates?limit=100`),
  ]);
  return { scenarios, runs, candidates };
}

export function newIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

import type {
  EvidenceResponse,
  ExploreResponse,
  Memo,
  PlaybookId,
  PlaybookRunRequest,
  PlaybookStreamEvent,
  ResolveResponse,
} from "./types";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) {
    throw new ApiError(`${res.status} ${res.statusText}`, res.status);
  }
  return (await res.json()) as T;
}

export function resolveEntity(query: string): Promise<ResolveResponse> {
  const params = new URLSearchParams({ q: query });
  return getJson<ResolveResponse>(`/api/resolve?${params.toString()}`);
}

export function getMemo(memoId: string): Promise<Memo> {
  return getJson<Memo>(`/api/memo/${encodeURIComponent(memoId)}`);
}

export function getEvidence(queryId: string): Promise<EvidenceResponse> {
  return getJson<EvidenceResponse>(`/api/evidence/${encodeURIComponent(queryId)}`);
}

export function getExplore(entityId: string, months = 36): Promise<ExploreResponse> {
  const params = new URLSearchParams({ months: String(months) });
  return getJson<ExploreResponse>(
    `/api/explore/${encodeURIComponent(entityId)}?${params.toString()}`,
  );
}

/**
 * Kicks off a playbook run via POST and streams back Server-Sent Events.
 * The backend streams `text/event-stream` frames directly from the POST
 * response body, so we can't use EventSource (no POST support) — instead we
 * read the raw ReadableStream and parse `data: {...}\n\n` frames ourselves.
 */
export async function runPlaybook(
  playbook: PlaybookId,
  body: PlaybookRunRequest,
  onEvent: (event: PlaybookStreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`/api/playbooks/${playbook}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });

  if (!res.ok || !res.body) {
    let detail = "";
    try {
      detail = await res.text();
    } catch {
      // ignore
    }
    throw new ApiError(
      detail || `${res.status} ${res.statusText}`,
      res.status,
    );
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE frames are separated by a blank line.
    let sepIndex: number;
    while ((sepIndex = buffer.indexOf("\n\n")) !== -1) {
      const rawFrame = buffer.slice(0, sepIndex);
      buffer = buffer.slice(sepIndex + 2);
      const dataLines = rawFrame
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trim());
      if (dataLines.length === 0) continue;
      const payload = dataLines.join("\n");
      try {
        const parsed = JSON.parse(payload) as PlaybookStreamEvent;
        onEvent(parsed);
      } catch {
        // Non-JSON / keep-alive frame — ignore.
      }
    }
  }

  // Flush any trailing partial frame that never got its blank-line terminator.
  const tail = buffer.trim();
  if (tail.startsWith("data:")) {
    const payload = tail.slice(5).trim();
    try {
      const parsed = JSON.parse(payload) as PlaybookStreamEvent;
      onEvent(parsed);
    } catch {
      // ignore
    }
  }
}

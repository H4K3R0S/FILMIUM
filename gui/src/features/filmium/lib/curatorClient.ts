// Klijent za Kurator komande: prepoznavanje, potvrda upisa, opovrgavanje.
export interface CuratorResult {
  kind: "answer" | "proposal" | "navigate";
  intent: string;
  params: Record<string, unknown>;
  reply: string;
  preview: Record<string, unknown> | null;
  confirm_token: string | null;
  sources: string[];
  log_id: string | null;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`Kurator zahtev nije uspeo: ${response.status}`);
  return (await response.json()) as T;
}

export function sendCommand(message: string): Promise<CuratorResult> {
  return post<CuratorResult>("/api/v1/filmium/curator/command", { message });
}

export function confirmAction(token: string): Promise<{ updated: boolean; media_id?: number }> {
  return post("/api/v1/filmium/curator/confirm", { token });
}

export function refuteAction(logId?: string): Promise<{ refuted: boolean }> {
  return post("/api/v1/filmium/curator/refute", { log_id: logId ?? null });
}

// ==========          HTTP KONFIGURACIJA          ==========

const API_BASE_URL =
  import.meta.env.VITE_CORE_API_URL ?? "http://127.0.0.1:8000";


// ==========          API GREŠKA          ==========

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);

    this.name = "ApiError";
    this.status = status;
  }
}

/**
 * Pravi kompletan URL prema jednom CORE API resursu.
 */
export function getApiUrl(endpoint: string): string {
  return `${API_BASE_URL}${endpoint}`;
}



// ==========          OSNOVNI HTTP ZAHTEV          ==========

/**
 * Šalje zahtev CORE API-ju i vraća parsirani JSON odgovor.
 */
async function requestJson<T>(
  endpoint: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(getApiUrl(endpoint), options);

  if (!response.ok) {
    let message =
      `CORE API greška: ${response.status} ${response.statusText}`;

    try {
      const errorData = (await response.json()) as {
        detail?: unknown;
      };

      if (typeof errorData.detail === "string") {
        message = errorData.detail;
      }
    } catch {
      // Odgovor nema JSON telo, pa zadržavamo osnovnu HTTP poruku.
    }

    throw new ApiError(message, response.status);
  }
    if (response.status === 204) {
        return undefined as T;
    }
  return response.json() as Promise<T>;
}


// ==========          JAVNE HTTP FUNKCIJE          ==========

/**
 * Šalje GET zahtev CORE API-ju.
 */
export function getJson<T>(endpoint: string): Promise<T> {
  return requestJson<T>(endpoint);
}

/**
 * Šalje POST zahtev sa JSON podacima CORE API-ju.
 */
export function postJson<TResponse, TRequest>(
  endpoint: string,
  body: TRequest,
): Promise<TResponse> {
  return requestJson<TResponse>(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
}


/**
 * Šalje PUT zahtev sa JSON podacima CORE API-ju.
 */
export function putJson<TResponse, TRequest>(
  endpoint: string,
  body: TRequest,
): Promise<TResponse> {
  return requestJson<TResponse>(endpoint, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
}




/**
 * Šalje PATCH zahtev sa JSON podacima CORE API-ju.
 */
export function patchJson<TResponse, TRequest>(
  endpoint: string,
  body: TRequest,
): Promise<TResponse> {
  return requestJson<TResponse>(endpoint, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
}





/**
 * Šalje DELETE zahtev CORE API-ju.
 */
export function deleteRequest<TResponse = void>(
  endpoint: string,
): Promise<TResponse> {
  return requestJson<TResponse>(endpoint, {
    method: "DELETE",
  });
}


/**
 * Šalje POST zahtev bez JSON tela CORE API-ju.
 */
export function postRequest<TResponse>(
  endpoint: string,
): Promise<TResponse> {
  return requestJson<TResponse>(endpoint, {
    method: "POST",
  });
}


// ==========          SSE (STVARNI PROGRES)          ==========

export interface SseProgress {
  files_done: number;
  files_total: number;
  file_done: number;
  file_total: number;
}

/**
 * Ukupni progres (ceo prenos) — glatko, uz udeo tekućeg fajla.
 */
export function sseOverallPercent(progress: SseProgress): number {
  if (progress.files_total <= 0) {
    return 0;
  }
  const fileFraction =
    progress.file_total > 0 ? progress.file_done / progress.file_total : 1;
  return Math.round(
    ((progress.files_done + fileFraction) / progress.files_total) * 100,
  );
}

/**
 * Progres tekućeg (pojedinačnog) fajla.
 */
export function sseFilePercent(progress: SseProgress): number {
  if (progress.file_total <= 0) {
    return 100;
  }
  return Math.round((progress.file_done / progress.file_total) * 100);
}

/**
 * Parsira jedan SSE blok („event: ...\ndata: ...") u par tipa i podataka.
 */
function parseSseChunk(
  chunk: string,
): { event: string | null; data: unknown } {
  let event: string | null = null;
  const dataLines: string[] = [];

  for (const line of chunk.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  }

  if (dataLines.length === 0) {
    return { event, data: null };
  }

  try {
    return { event, data: JSON.parse(dataLines.join("\n")) };
  } catch {
    return { event, data: null };
  }
}

/**
 * POST koji čita SSE stream: zove ``onProgress`` po fajlu i vraća telo
 * ``done`` događaja kao rezultat. ``error`` događaj baca ApiError.
 */
export async function postSse<TResult, TBody>(
  endpoint: string,
  body: TBody,
  onProgress: (progress: SseProgress) => void,
): Promise<TResult> {
  const response = await fetch(getApiUrl(endpoint), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!response.ok || response.body === null) {
    let message =
      `CORE API greška: ${response.status} ${response.statusText}`;
    try {
      const errorData = (await response.json()) as { detail?: unknown };
      if (typeof errorData.detail === "string") {
        message = errorData.detail;
      }
    } catch {
      // Bez JSON tela — zadržavamo osnovnu poruku.
    }
    throw new ApiError(message, response.status);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: TResult | undefined;
  let errorMessage: string | null = null;

  for (;;) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });

    let separatorIndex = buffer.indexOf("\n\n");
    while (separatorIndex !== -1) {
      const chunk = buffer.slice(0, separatorIndex);
      buffer = buffer.slice(separatorIndex + 2);
      const { event, data } = parseSseChunk(chunk);

      if (event === "progress" && data !== null) {
        onProgress(data as SseProgress);
      } else if (event === "done") {
        result = data as TResult;
      } else if (event === "error") {
        errorMessage =
          (data as { message?: string } | null)?.message ??
          "Uvoz nije uspeo.";
      }

      separatorIndex = buffer.indexOf("\n\n");
    }
  }

  if (errorMessage !== null) {
    throw new ApiError(errorMessage, 422);
  }
  if (result === undefined) {
    throw new ApiError("Nepotpun odgovor servera (SSE).", 500);
  }
  return result;
}


/**
 * Šalje POST zahtev sa multipart form podacima.
 *
 * Content-Type se ne postavlja ručno zato što browser mora sam
 * da doda odgovarajući multipart boundary.
 */
export function postFormData<TResponse>(
  endpoint: string,
  body: FormData,
): Promise<TResponse> {
  return requestJson<TResponse>(endpoint, {
    method: "POST",
    body,
  });
}
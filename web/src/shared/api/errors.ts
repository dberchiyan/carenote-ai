import type { components } from "./schema";

export type ErrorCode = components["schemas"]["ErrorCode"];
export type ErrorBody = components["schemas"]["ErrorOut"];

/**
 * Every API refusal: the HTTP status, a closed `code` to branch on (never match on the message
 * text), a human message, and structured details (the note's status, the invalid fields).
 */
export class ApiError extends Error {
  readonly code: ErrorCode;
  readonly details: Record<string, unknown>;

  constructor(
    readonly status: number,
    body: Partial<ErrorBody> | undefined,
    fallbackMessage: string,
  ) {
    super(body?.message ?? fallbackMessage);
    this.name = "ApiError";
    this.code = body?.code ?? (status >= 500 ? "internal_error" : "validation_error");
    this.details = body?.details ?? {};
  }

  /** The field messages of a validation error, by dotted path (`body.username`). */
  get fields(): { path: string; message: string }[] {
    const raw = this.details.fields;
    return Array.isArray(raw) ? (raw as { path: string; message: string }[]) : [];
  }
}

export function isApiError(error: unknown, code?: ErrorCode): error is ApiError {
  return error instanceof ApiError && (code === undefined || error.code === code);
}

function parseBody(error: unknown): Partial<ErrorBody> | undefined {
  if (typeof error !== "object" || error === null) return undefined;
  const { code, message, details } = error as Record<string, unknown>;
  if (typeof code !== "string" || typeof message !== "string") return undefined;
  return {
    code: code as ErrorCode,
    message,
    details:
      typeof details === "object" && details !== null ? (details as ErrorBody["details"]) : {},
  };
}

type Result<T> = { data?: T; error?: unknown; response: Response };

/** Return data or throw an ApiError carrying the HTTP status and the API's error body. */
export function unwrap<T>({ data, error, response }: Result<T>): T {
  if (error !== undefined || data === undefined) {
    if (response.ok && error === undefined) return undefined as T; // 204 No Content
    throw new ApiError(response.status, parseBody(error), `Request failed (${response.status})`);
  }
  return data;
}

/** For the few calls made with raw `fetch` (multipart upload): same error, same shape. */
export async function throwIfNotOk(response: Response, fallback: string): Promise<void> {
  if (response.ok) return;
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    body = undefined;
  }
  throw new ApiError(response.status, parseBody(body), `${fallback} (${response.status})`);
}

/** TanStack `retry`: a 4xx answer is final (no access, not found, invalid); 5xx/network get one more try. */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiError && error.status < 500) return false;
  return failureCount < 1;
}

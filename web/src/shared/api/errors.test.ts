import { describe, expect, it } from "vitest";

import { ApiError, isApiError, shouldRetry, throwIfNotOk, unwrap } from "@/shared/api/errors";

const body = (status: number, json: unknown) =>
  new Response(JSON.stringify(json), { status, headers: { "content-type": "application/json" } });

describe("unwrap", () => {
  it("turns the API's error body into an ApiError with code and details", () => {
    const error = {
      code: "invalid_state",
      message: "Note is rejected",
      details: { status: "rejected" },
    };
    expect(() => unwrap({ error, response: body(409, error) })).toThrow(ApiError);
    try {
      unwrap({ error, response: body(409, error) });
    } catch (e) {
      expect(isApiError(e, "invalid_state")).toBe(true);
      expect((e as ApiError).message).toBe("Note is rejected");
      expect((e as ApiError).details).toEqual({ status: "rejected" });
    }
  });

  it("falls back to a status message when the body is not ours (proxy, gateway)", () => {
    try {
      unwrap({ error: "<html>bad gateway</html>", response: body(502, {}) });
    } catch (e) {
      expect((e as ApiError).code).toBe("internal_error");
      expect((e as ApiError).message).toBe("Request failed (502)");
    }
  });

  it("exposes validation fields", () => {
    const error = {
      code: "validation_error",
      message: "The request was not valid.",
      details: {
        fields: [{ path: "body.username", message: "too short", type: "string_too_short" }],
      },
    };
    try {
      unwrap({ error, response: body(422, error) });
    } catch (e) {
      expect((e as ApiError).fields).toEqual([expect.objectContaining({ path: "body.username" })]);
    }
  });
});

describe("throwIfNotOk", () => {
  it("passes a 2xx and throws the same ApiError for a raw fetch", async () => {
    await expect(throwIfNotOk(body(200, {}), "Upload failed")).resolves.toBeUndefined();
    const error = { code: "payload_rejected", message: "The file is empty.", details: {} };
    await expect(throwIfNotOk(body(422, error), "Upload failed")).rejects.toMatchObject({
      code: "payload_rejected",
      message: "The file is empty.",
    });
  });
});

describe("shouldRetry", () => {
  const refusal = (status: number) => new ApiError(status, undefined, "refused");

  it("does not retry a refusal: 403 and 404 will not change on the second try", () => {
    expect(shouldRetry(0, refusal(403))).toBe(false);
    expect(shouldRetry(0, refusal(404))).toBe(false);
    expect(shouldRetry(0, refusal(422))).toBe(false);
  });

  it("retries a server or network failure once", () => {
    expect(shouldRetry(0, refusal(503))).toBe(true);
    expect(shouldRetry(0, new TypeError("Failed to fetch"))).toBe(true);
    expect(shouldRetry(1, new TypeError("Failed to fetch"))).toBe(false);
  });
});

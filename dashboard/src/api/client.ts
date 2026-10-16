import type { MockApi } from "./mock";

export const MOCK = import.meta.env.VITE_MOCK === "1";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

/** The server could not be reached at all (as opposed to answering with an error). */
export class UnreachableError extends Error {
  constructor() {
    super("Career Agent isn't running.");
  }
}

// The mock is only imported when VITE_MOCK=1, so production bundles do not contain it.
let mock: Promise<{ api: MockApi; mod: typeof import("./mock") }> | null = null;
function mockApi() {
  mock ??= import("./mock").then((mod) => {
    const q = new URLSearchParams(location.search);
    return { mod, api: mod.createMockApi({ onboarding: q.has("onboarding"), empty: q.has("empty"), offline: q.has("offline") }) };
  });
  return mock;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  if (MOCK) {
    const { api: m, mod } = await mockApi();
    try {
      return await m.request<T>(method, `/api${path}`, body);
    } catch (e) {
      if (e instanceof mod.MockUnreachable) throw new UnreachableError();
      if (e instanceof mod.MockHttpError) throw new ApiError(e.status, e.message);
      throw e;
    }
  }
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      method,
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new UnreachableError();
  }
  if (!res.ok) {
    let detail = res.statusText || "Something went wrong";
    try {
      const j = (await res.json()) as { detail?: unknown };
      if (typeof j.detail === "string") detail = j.detail;
    } catch {
      /* keep statusText */
    }
    // A dev proxy with no backend answers 502/504, which means "not running" too.
    if (res.status === 502 || res.status === 503 || res.status === 504) throw new UnreachableError();
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body ?? {}),
  put: <T>(path: string, body: unknown) => request<T>("PUT", path, body),
  patch: <T>(path: string, body: unknown) => request<T>("PATCH", path, body),
};

export function errorMessage(e: unknown): string {
  return e instanceof Error ? e.message : "Something went wrong";
}

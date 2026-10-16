import { beforeEach, describe, expect, it } from "vitest";
import { dateKey } from "../lib/format";
import { createMockApi, MockHttpError, MockUnreachable, type MockApi } from "./mock";
import type { CV, MemoryResponse, Project, ReviewItem, Session, Settings, Status, Today } from "./types";

// A fixed Wednesday afternoon so schedule-dependent assertions are stable.
const NOW = new Date(2026, 9, 14, 16, 20, 0);
let api: MockApi;
const get = <T,>(p: string) => api.request<T>("GET", `/api${p}`);
const post = <T,>(p: string, b?: unknown) => api.request<T>("POST", `/api${p}`, b ?? {});

beforeEach(() => {
  api = createMockApi({ now: NOW, latency: 0 });
});

describe("mock API", () => {
  it("reports status with a live current session", async () => {
    const s = await get<Status>("/status");
    expect(s.state).toBe("running");
    expect(s.profile_complete).toBe(true);
    expect(s.review_count).toBe(5);
    expect(s.current?.project).toBe("Mobile AI");
  });

  it("builds Today from sessions", async () => {
    const t = await get<Today>("/today");
    expect(t.date).toBe(dateKey(NOW));
    expect(t.name).toBe("Alex");
    expect(t.current_session?.is_open).toBe(true);
    expect(t.week).toHaveLength(7);
    expect(t.week[0]?.date <= t.date).toBe(true);
    expect(t.top_skills).toHaveLength(4);
    expect(t.ribbon.length).toBe(t.session_count);
  });

  it("returns sessions per day, empty on a past weekend", async () => {
    const today = await get<{ sessions: Session[] }>(`/sessions?date=${dateKey(NOW)}`);
    expect(today.sessions.length).toBe(7);
    const sat = await get<{ sessions: Session[] }>("/sessions?date=2026-10-10");
    expect(sat.sessions).toEqual([]);
  });

  it("serves raw events for one session", async () => {
    const { sessions } = await get<{ sessions: Session[] }>(`/sessions?date=${dateKey(NOW)}`);
    const first = sessions[0] as Session;
    const detail = await get<Session & { raw_events: unknown[] }>(`/sessions/${first.id}`);
    expect(detail.raw_events.length).toBeGreaterThan(0);
    await expect(get("/sessions/nope")).rejects.toBeInstanceOf(MockHttpError);
  });

  it("confirming a review item updates the session, queue and memory count", async () => {
    const before = await get<Status>("/status");
    const { items } = await get<{ items: ReviewItem[] }>("/review");
    const item = items.find((i) => i.kind === "session") as ReviewItem;
    const r = await post<{ ok: boolean; remaining: number }>(`/review/${item.id}`, { action: "confirm" });
    expect(r).toEqual({ ok: true, remaining: 4 });
    const s = await get<Session>(`/sessions/${item.ref_id}`);
    expect(s.state).toBe("confirmed");
    const after = await get<Status>("/status");
    expect(after.review_count).toBe(4);
    expect(after.memory_count).toBe(before.memory_count + 1);
  });

  it("rejects and answers questions", async () => {
    const { items } = await get<{ items: ReviewItem[] }>("/review");
    const q = items.find((i) => i.kind === "question") as ReviewItem;
    expect(q.options).toEqual(["Yes", "No"]);
    const r = await post<{ remaining: number }>(`/review/${q.id}`, { action: "answer", answer: "Yes" });
    expect(r.remaining).toBe(4);
    const sess = items.find((i) => i.kind === "session") as ReviewItem;
    await post(`/sessions/${sess.ref_id}/review`, { action: "reject" });
    expect((await get<Session>(`/sessions/${sess.ref_id}`)).state).toBe("rejected");
  });

  it("edits a session and moves it to another project", async () => {
    const { items } = await get<{ items: ReviewItem[] }>("/review");
    const sess = items.find((i) => i.kind === "session") as ReviewItem;
    const s = await post<Session>(`/sessions/${sess.ref_id}/review`, { action: "edit", activity: "Renamed", project_id: "p-field" });
    expect(s.activity).toBe("Renamed");
    expect(s.project?.name).toBe("Field Updates");
    expect(s.state).toBe("confirmed");
  });

  it("renames and merges projects", async () => {
    const renamed = await api.request<Project>("PATCH", "/api/projects/p-logs", { name: "Parser" });
    expect(renamed.name).toBe("Parser");
    const target = await post<Project>("/projects/p-logs/merge", { into_id: "p-field" });
    expect(target.id).toBe("p-field");
    const { projects } = await get<{ projects: Project[] }>("/projects");
    expect(projects.map((p) => p.id)).not.toContain("p-logs");
    await expect(post("/projects/p-field/merge", { into_id: "p-field" })).rejects.toBeInstanceOf(MockHttpError);
  });

  it("only stores user-entered impact on achievements", async () => {
    const { achievements } = await get<{ achievements: { id: string; impact: string | null }[] }>("/achievements");
    expect(achievements.find((a) => a.id === "a-temp")?.impact).toBeNull();
    const a = await api.request<{ impact: string | null; on_cv: boolean }>("PATCH", "/api/achievements/a-temp", { impact: " Saved 3h per run ", on_cv: true });
    expect(a.impact).toBe("Saved 3h per run");
    expect(a.on_cv).toBe(true);
  });

  it("filters memory by state and counts per state", async () => {
    const all = await get<MemoryResponse>("/memory");
    const inferred = await get<MemoryResponse>("/memory?state=inferred");
    expect(inferred.items.every((i) => i.state === "inferred")).toBe(true);
    expect(inferred.items.length).toBe(all.counts.inferred);
    expect(Object.keys(all.counts).sort()).toEqual(["confirmed", "inferred", "observed", "rejected"]);
  });

  it("supports pause and resume", async () => {
    const p = await post<Status>("/agent/pause", { minutes: 60 });
    expect(p.state).toBe("paused");
    expect(p.paused_until).not.toBeNull();
    expect(p.current).toBeNull();
    expect((await post<Status>("/agent/resume")).state).toBe("running");
  });

  it("regenerates the CV, then marks edited bullets confirmed", async () => {
    const cv = await get<CV>("/cv");
    const ids = cv.experience.flatMap((e) => e.bullets.map((b) => b.id));
    const next = await post<CV>("/cv/regenerate");
    const nextIds = next.experience.flatMap((e) => e.bullets.map((b) => b.id));
    expect(nextIds.some((i) => !ids.includes(i))).toBe(true);
    const weak = nextIds.includes("b-mob-1") ? "b-mob-1" : "b-sup-3";
    const patched = await api.request<CV>("PATCH", `/api/cv/bullets/${weak}`, { text: "Edited by hand." });
    expect(patched.experience.flatMap((e) => e.bullets).find((b) => b.id === weak)?.state).toBe("confirmed");
  });

  it("aggregates insights for week and month", async () => {
    const w = await get<{ by_day: unknown[]; projects: { share: number }[] }>("/insights?period=week");
    const m = await get<{ by_day: unknown[] }>("/insights?period=month");
    expect(w.by_day).toHaveLength(7);
    expect(m.by_day).toHaveLength(30);
    expect(w.projects.reduce((a, p) => a + p.share, 0)).toBeCloseTo(1, 5);
  });

  it("saves profile and settings", async () => {
    const onboarding = createMockApi({ now: NOW, latency: 0, onboarding: true });
    expect((await onboarding.request<Status>("GET", "/api/status")).profile_complete).toBe(false);
    const profile = await onboarding.request<{ setup_at: string | null }>("PUT", "/api/profile", { name: "Ada", job_title: "", focus: "", projects: [], tools: [], screen_understanding: false, autostart: true, ai_provider: "none", language: "en", setup_at: null });
    expect(profile.setup_at).not.toBeNull();
    expect((await onboarding.request<Status>("GET", "/api/status")).profile_complete).toBe(true);
    const s = await get<Settings>("/settings");
    const saved = await api.request<Settings>("PUT", "/api/settings", { ...s, privacy: { ...s.privacy, browser_tracking: false } });
    expect(saved.privacy.browser_tracking).toBe(false);
    await expect(post<{ analyzed: number }>("/analyze")).resolves.toEqual({ analyzed: 0, pending: 0 });
  });

  it("can simulate an unreachable server", async () => {
    api.setOffline(true);
    await expect(get("/status")).rejects.toBeInstanceOf(MockUnreachable);
  });
});

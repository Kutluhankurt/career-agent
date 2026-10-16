import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient, type QueryKey } from "@tanstack/react-query";
import { api, MOCK, UnreachableError } from "./client";
import type {
  Achievement,
  CV,
  Insights,
  MemoryResponse,
  Profile,
  Project,
  ProjectDetail,
  ReviewItem,
  Session,
  SessionDetail,
  Settings,
  Skill,
  Status,
  Today,
  TruthState,
} from "./types";

const STATUS_KEY = ["status"] as const;

/** Whether the SSE stream is currently delivering; polling kicks in when it is not. */
let sseConnected = false;
const sseListeners = new Set<() => void>();
const setSse = (v: boolean) => {
  if (sseConnected === v) return;
  sseConnected = v;
  sseListeners.forEach((l) => l());
};

export function useStatus() {
  const [connected, setConnected] = useState(sseConnected);
  useEffect(() => {
    const l = () => setConnected(sseConnected);
    sseListeners.add(l);
    return () => void sseListeners.delete(l);
  }, []);
  return useQuery({
    queryKey: STATUS_KEY,
    queryFn: () => api.get<Status>("/status"),
    retry: false,
    // Poll every 10s as a fallback, or faster while offline so the page recovers by itself.
    refetchInterval: (q) => (q.state.status === "error" ? 4000 : connected ? false : 10_000),
    staleTime: 2000,
  });
}

/** Subscribes to /api/stream and pushes status events into the query cache. */
export function useLiveStatus() {
  const qc = useQueryClient();
  useEffect(() => {
    if (MOCK || typeof EventSource === "undefined") return;
    const es = new EventSource("/api/stream");
    let last: Status | undefined;
    es.addEventListener("open", () => setSse(true));
    es.addEventListener("error", () => setSse(false));
    es.addEventListener("status", (ev) => {
      try {
        const s = JSON.parse((ev as MessageEvent<string>).data) as Status;
        setSse(true);
        qc.setQueryData(STATUS_KEY, s);
        // Only refresh dependent data when something actually changed; lists do not re-animate every tick.
        if (last && (last.sessions_today !== s.sessions_today || last.review_count !== s.review_count || last.memory_count !== s.memory_count)) {
          for (const k of ["today", "sessions", "review", "memory", "projects", "skills", "achievements"]) void qc.invalidateQueries({ queryKey: [k] });
        }
        last = s;
      } catch {
        /* ignore malformed event */
      }
    });
    return () => {
      es.close();
      setSse(false);
    };
  }, [qc]);
}

export const useToday = (date?: string) =>
  useQuery({ queryKey: ["today", date ?? "now"], queryFn: () => api.get<Today>(`/today${date ? `?date=${date}` : ""}`), refetchInterval: 30_000 });

export const useSessions = (date: string) =>
  useQuery({
    queryKey: ["sessions", date],
    queryFn: () => api.get<{ date: string; sessions: Session[] }>(`/sessions?date=${date}`),
    refetchInterval: 30_000,
  });

export const useSessionDetail = (id: string | null, enabled: boolean) =>
  useQuery({ queryKey: ["session", id], queryFn: () => api.get<SessionDetail>(`/sessions/${id}`), enabled: enabled && !!id });

export const useReview = () => useQuery({ queryKey: ["review"], queryFn: () => api.get<{ items: ReviewItem[] }>("/review") });
export const useProjects = () => useQuery({ queryKey: ["projects"], queryFn: () => api.get<{ projects: Project[] }>("/projects") });
export const useProject = (id: string | null) =>
  useQuery({ queryKey: ["project", id], queryFn: () => api.get<ProjectDetail>(`/projects/${id}`), enabled: !!id });
export const useSkills = () => useQuery({ queryKey: ["skills"], queryFn: () => api.get<{ skills: Skill[] }>("/skills") });
export const useAchievements = () => useQuery({ queryKey: ["achievements"], queryFn: () => api.get<{ achievements: Achievement[] }>("/achievements") });
export const useMemory = (state?: TruthState | "") =>
  useQuery({ queryKey: ["memory", state ?? ""], queryFn: () => api.get<MemoryResponse>(`/memory${state ? `?state=${state}` : ""}`) });
export const useInsights = (period: "week" | "month") =>
  useQuery({ queryKey: ["insights", period], queryFn: () => api.get<Insights>(`/insights?period=${period}`) });
export const useCV = () => useQuery({ queryKey: ["cv"], queryFn: () => api.get<CV>("/cv") });
export const useProfile = () => useQuery({ queryKey: ["profile"], queryFn: () => api.get<Profile>("/profile") });
export const useSettings = () => useQuery({ queryKey: ["settings"], queryFn: () => api.get<Settings>("/settings") });

/** Invalidate everything that a change to career memory can affect. */
function useRefresh() {
  const qc = useQueryClient();
  return (except: string[] = []) => {
    const skip = new Set(except);
    for (const k of ["status", "today", "sessions", "session", "review", "projects", "project", "skills", "achievements", "memory", "insights", "cv"]) {
      if (!skip.has(k)) void qc.invalidateQueries({ queryKey: [k] });
    }
  };
}

export function useSetStatus() {
  const qc = useQueryClient();
  return (fn: (s: Status) => Status) => qc.setQueryData<Status>(STATUS_KEY, (s) => (s ? fn(s) : s));
}

export function usePause() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (minutes: number) => api.post<Status>("/agent/pause", { minutes }),
    onSuccess: (s) => qc.setQueryData(STATUS_KEY, s),
  });
}
export function useResume() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: () => api.post<Status>("/agent/resume"), onSuccess: (s) => qc.setQueryData(STATUS_KEY, s) });
}

export interface SessionReviewBody {
  action: "confirm" | "reject" | "edit";
  activity?: string;
  project_id?: string;
  skills?: string[];
}
export function useReviewSession() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: ({ id, ...body }: SessionReviewBody & { id: string }) => api.post<Session>(`/sessions/${id}/review`, body),
    onSuccess: () => refresh(),
  });
}

export interface ReviewBody {
  action: "confirm" | "reject" | "edit" | "answer";
  title?: string;
  answer?: string;
}
/** Review-queue POST. Does not refetch `review`: the page keeps its own local queue. */
export function useReviewItem() {
  const refresh = useRefresh();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: ReviewBody & { id: string }) => api.post<{ ok: true; remaining: number }>(`/review/${id}`, body),
    onSuccess: (_r, v) => {
      qc.setQueryData<{ items: ReviewItem[] }>(["review"], (d) => (d ? { items: d.items.filter((i) => i.id !== v.id) } : d));
      refresh(["review"]);
    },
  });
}

export function usePatchProject() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string; name?: string; state?: TruthState }) => api.patch<Project>(`/projects/${id}`, body),
    onSuccess: () => refresh(),
  });
}
export function useMergeProject() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: ({ id, into_id }: { id: string; into_id: string }) => api.post<Project>(`/projects/${id}/merge`, { into_id }),
    onSuccess: () => refresh(),
  });
}
export function usePatchSkill() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: ({ id, state }: { id: string; state: TruthState }) => api.patch<Skill>(`/skills/${id}`, { state }),
    onSuccess: () => refresh(),
  });
}
export function usePatchAchievement() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string; title?: string; state?: TruthState; impact?: string | null; on_cv?: boolean }) =>
      api.patch<Achievement>(`/achievements/${id}`, body),
    onSuccess: () => refresh(),
  });
}
export function useRegenerateCV() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: () => api.post<CV>("/cv/regenerate"), onSuccess: (cv) => qc.setQueryData(["cv"], cv) });
}
export function usePatchBullet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, text }: { id: string; text: string }) => api.patch<CV>(`/cv/bullets/${id}`, { text }),
    onSuccess: (cv) => qc.setQueryData(["cv"], cv),
  });
}
export function useSaveProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (p: Profile) => api.put<Profile>("/profile", p),
    onSuccess: (p) => {
      qc.setQueryData(["profile"], p);
      void qc.invalidateQueries({ queryKey: STATUS_KEY });
    },
  });
}
export function useSaveSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (s: Settings) => api.put<Settings>("/settings", s),
    onMutate: (s) => qc.setQueryData(["settings"], s),
    onSuccess: (s) => {
      qc.setQueryData(["settings"], s);
      void qc.invalidateQueries({ queryKey: STATUS_KEY });
    },
    onError: () => void qc.invalidateQueries({ queryKey: ["settings"] }),
  });
}
export function useAnalyze() {
  const refresh = useRefresh();
  return useMutation({ mutationFn: () => api.post<{ analyzed: number; pending: number }>("/analyze", {}), onSuccess: () => refresh() });
}

export const isUnreachable = (e: unknown) => e instanceof UnreachableError;
export type { QueryKey };

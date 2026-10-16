// Mirrors docs/API.md field for field. Do not edit without updating the contract.

export type TruthState = "observed" | "inferred" | "confirmed" | "rejected";

export type EvidenceType =
  | "application" | "window" | "file" | "git" | "browser" | "ticket" | "command" | "user_confirmation";

export interface Evidence {
  id: string;
  type: EvidenceType;
  value: string;            // "AI-1842", "temperature_test.py", "abc123 Fix temperature validation"
  label: string;            // human label, e.g. "Ticket", "File", "Commit", "Command", "Site"
  observed_at: string | null;
  session_id: string | null;
}

export interface ProjectRef { id: string; name: string; color: number }   // color = palette index 0..7

export interface Session {
  id: string;
  start: string;
  end: string;
  active_seconds: number;
  idle_seconds: number;
  is_open: boolean;              // still running right now
  label: string;                 // rule label: "supervisor · AI-1842"
  activity: string;              // understood activity: "Supervisor temperature testing"
  category: string;              // "Testing" | "Development" | "Investigation" | "Communication" | ...
  project: ProjectRef | null;
  state: TruthState;
  confidence: number;            // 0..1
  score: number;                 // 0..1 rule coherence
  skills: string[];
  evidence: Evidence[];
  applications: Record<string, number>;   // app -> seconds, largest first
  files: string[];
  tickets: string[];
  workspaces: string[];
  analyzed_by: string | null;    // "rules" | "claude" | "openai" | "gemini" | "local" | null
}

export interface RawEvent { timestamp: string; type: string; application: string | null; title: string | null }

export interface SkillSummary { name: string; score: number; delta: number }   // score 0..100, delta vs 7 days ago

export interface AchievementStep { name: "problem" | "investigation" | "implementation" | "testing" | "verification"; done: boolean; evidence: Evidence[] }

export interface Achievement {
  id: string;
  title: string;
  project: ProjectRef | null;
  ticket: string | null;
  state: TruthState;
  confidence: number;
  steps: AchievementStep[];
  impact: string | null;         // user-entered only, never generated
  on_cv: boolean;
  created_at: string;
}

export interface Project {
  id: string;
  name: string;
  state: TruthState;
  color: number;
  aliases: string[];             // workspaces / repos / ticket prefixes that map to it
  active_seconds: number;
  session_count: number;
  tickets: string[];
  repos: string[];
  skills: string[];
  achievement_count: number;
  sparkline: number[];           // active seconds per day, last 30 days, oldest first
  last_active: string | null;
}

export interface Skill {
  id: string;
  name: string;
  category: string;              // "Language" | "Tool" | "Practice" | "Domain"
  state: TruthState;
  score: number;                 // 0..100
  previous_score: number;        // 7 days ago
  factors: { frequency: number; duration: number; complexity: number; diversity: number; evidence: number; confirmation: number }; // each 0..1
  history: { date: string; score: number }[];   // last 30 days, date = "YYYY-MM-DD"
  projects: string[];
  evidence_count: number;
  active_seconds: number;
}

export interface ReviewItem {
  id: string;
  kind: "session" | "project" | "skill" | "achievement" | "question";
  ref_id: string;                // id of the session/project/skill/achievement
  title: string;                 // "Supervisor temperature testing" or the question text
  subtitle: string;              // "Session · 09:12–10:04" / "Question from Learning mode"
  project: ProjectRef | null;
  confidence: number;
  skills: string[];
  evidence: Evidence[];
  options: string[] | null;      // for questions: ["Yes", "No"]; otherwise null
  created_at: string;
}

export interface Status {
  version: string;
  platform: string;              // "Linux" | "macOS" | "Windows"
  state: "running" | "paused" | "stopped";
  pid: number | null;
  uptime_seconds: number | null;
  paused_until: string | null;
  events_today: number;
  sessions_today: number;
  review_count: number;
  memory_count: number;          // confirmed + observed facts in Career Memory
  current: { application: string | null; title: string | null; project: string | null; since: string } | null;
  ai: { provider: string; available: boolean; pending_sessions: number };
  learning: { active: boolean; day: number; days_total: number };
  profile_complete: boolean;     // false → dashboard shows onboarding
}

export interface Today {
  date: string;
  name: string | null;                        // first name from profile
  active_seconds: number;
  session_count: number;
  project_count: number;
  ribbon: { start: string; end: string; color: number | null; label: string }[];
  current_session: Session | null;
  review_count: number;
  top_skills: SkillSummary[];                 // up to 4
  week: { date: string; active_seconds: number }[];   // Monday..Sunday of this week
  week_total_seconds: number;
  potential_achievements: Achievement[];      // up to 3
}

export interface MemoryItem {
  id: string;
  type: "project" | "skill" | "achievement" | "technology" | "evidence" | "session";
  name: string;
  state: TruthState;
  project: string | null;
  detail: string;                             // e.g. "43h · 31 sessions" or "Python · 78"
  updated_at: string;
}

export interface Insights {
  period: "week" | "month";
  start: string; end: string;                 // dates
  active_seconds: number;
  session_count: number;
  projects: { name: string; color: number; seconds: number; share: number }[];
  top_activities: { name: string; seconds: number; count: number }[];
  skills_up: SkillSummary[];
  skills_down: SkillSummary[];
  achievements: Achievement[];
  repeated: string[];                         // "8 testing sessions on Supervisor"
  stopped: string[];                          // "No Mobile AI work since 2 Oct"
  cv_candidates: number;
  by_day: { date: string; active_seconds: number }[];
}

export interface CVBullet { id: string; text: string; confidence: number; state: TruthState; evidence: Evidence[]; weak: boolean }
export interface CV {
  name: string; title: string; summary: string;
  experience: { project: string; color: number; bullets: CVBullet[] }[];
  skills: string[];
  generated_at: string | null;
}

export interface Profile {
  name: string; job_title: string; focus: string;
  projects: string[]; tools: string[];
  screen_understanding: boolean; autostart: boolean;
  ai_provider: "claude" | "gemini" | "openai" | "local" | "none";
  language: "en" | "tr";
  setup_at: string | null;
}

export interface Settings {
  general: { language: string; timezone: string };
  collector: { interval: number; idle_threshold: number; repo_roots: string[]; excluded_apps: string[] };
  sessions: { split_gap: number; switch_min: number; min_session: number };
  privacy: { screen_understanding: boolean; browser_tracking: boolean; file_tracking: boolean };
  ai: { provider: string; model: string; analysis_interval: number; key_configured: boolean };
  server: { host: string; port: number };
}

export type ReviewAction = "confirm" | "reject" | "edit";
export type SessionDetail = Session & { raw_events: RawEvent[] };
export type ProjectDetail = Project & { sessions: Session[]; achievements: Achievement[] };
export interface MemoryResponse { items: MemoryItem[]; counts: Record<TruthState, number> }

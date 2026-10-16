import { describe, expect, it } from "vitest";
import { addDays, confidenceLabel, confidenceWord, dateKey, formatClock, formatDuration, formatHours, greeting, plural, projectColor, relativeTime, stateLabel } from "./format";

describe("formatDuration", () => {
  it("formats hours and minutes", () => {
    expect(formatDuration(24120)).toBe("6h 42m");
    expect(formatDuration(3600)).toBe("1h");
    expect(formatDuration(3660)).toBe("1h 1m");
    expect(formatDuration(42 * 60)).toBe("42m");
  });
  it("handles zero and sub-minute values", () => {
    expect(formatDuration(0)).toBe("0m");
    expect(formatDuration(-5)).toBe("0m");
    expect(formatDuration(40)).toBe("<1m");
  });
  it("formats a ticking clock", () => {
    expect(formatClock(32 * 60 + 14)).toBe("00:32:14");
    expect(formatClock(3 * 3600 + 5)).toBe("03:00:05");
  });
  it("formats hours compactly", () => {
    expect(formatHours(43 * 3600 + 900)).toBe("43h");
    expect(formatHours(5400)).toBe("1.5h");
  });
});

describe("confidence words", () => {
  it("uses the documented thresholds", () => {
    expect(confidenceWord(0.95)).toBe("Very likely");
    expect(confidenceWord(0.949)).toBe("Very likely"); // rounds to 95
    expect(confidenceWord(0.94)).toBe("Likely");
    expect(confidenceWord(0.8)).toBe("Likely");
    expect(confidenceWord(0.79)).toBe("Possibly");
    expect(confidenceWord(0.6)).toBe("Possibly");
    expect(confidenceWord(0.59)).toBe("Unsure");
    expect(confidenceWord(0)).toBe("Unsure");
  });
  it("renders word and percent", () => {
    expect(confidenceLabel(0.86)).toBe("Likely · 86%");
    expect(confidenceLabel(1.4)).toBe("Very likely · 100%");
  });
  it("labels truth states in plain words", () => {
    expect(stateLabel("inferred")).toBe("Needs review");
    expect(stateLabel("confirmed")).toBe("Confirmed");
    expect(stateLabel("rejected")).toBe("Not right");
  });
});

describe("dates and misc", () => {
  it("keeps local date keys stable across day arithmetic", () => {
    expect(addDays("2026-10-16", -1)).toBe("2026-10-15");
    expect(addDays("2026-10-31", 1)).toBe("2026-11-01");
    expect(dateKey(new Date(2026, 0, 5))).toBe("2026-01-05");
  });
  it("greets by hour", () => {
    expect(greeting(8)).toBe("Good morning");
    expect(greeting(14)).toBe("Good afternoon");
    expect(greeting(20)).toBe("Good evening");
  });
  it("maps project colours onto the 8-hue palette", () => {
    expect(projectColor(0)).toBe("var(--p1)");
    expect(projectColor(9)).toBe("var(--p2)");
    expect(projectColor(null)).toBe("var(--faint)");
  });
  it("pluralises and formats relative times", () => {
    expect(plural(1, "session")).toBe("1 session");
    expect(plural(3, "session")).toBe("3 sessions");
    const now = new Date("2026-10-16T12:00:00Z");
    expect(relativeTime("2026-10-16T11:30:00Z", now)).toBe("30m ago");
    expect(relativeTime("2026-10-15T09:00:00Z", now)).toBe("Yesterday");
  });
});

// Progress of a skill toward its next proficiency level. Mirrors the backend
// thresholds in store.skill_level: novice (<3 uses) → proficient (3) → expert (8).
export interface SkillInfo {
  name: string; description?: string; uses?: number; stars?: number;
  level?: string; successes?: number; failures?: number; trigger?: string; source?: string;
}

export function skillProgress(s: SkillInfo): { pct: number; next: string } {
  const uses = s.uses ?? 0;
  const stars = s.stars ?? 1;
  if (stars >= 3) return { pct: 100, next: "max" };
  if (stars === 2) return { pct: Math.min(100, Math.round(((uses - 3) / 5) * 100)), next: "expert" };
  return { pct: Math.min(100, Math.round((uses / 3) * 100)), next: "proficient" };
}

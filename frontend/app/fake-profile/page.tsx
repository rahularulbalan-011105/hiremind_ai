"use client";

import Link from "next/link";
import { useState } from "react";
import { callJson, type ApiResult } from "@/lib/api";

type Severity = "low" | "medium" | "high";
type RiskLevel = "low" | "medium" | "high";

type CandidateSummary = {
  full_name: string;
  email: string | null;
  phone: string | null;
  headline: string | null;
  location: string | null;
  skill_count: number;
  experience_years: number;
  education_count: number;
  raw_resume_url: string | null;
};

type SignalBreakdown = {
  signal: string;
  fired: boolean;
  penalty: number;
  severity: Severity | null;
  message: string;
  details: Record<string, unknown>;
};

type GitHubCheck = {
  checked: boolean;
  username: string | null;
  profile_url: string | null;
  account_age_days: number | null;
  public_repos: number | null;
  followers: number | null;
  top_languages: string[];
  claimed_skills_found_in_repos: string[];
  claimed_skills_missing_in_repos: string[];
  warnings: string[];
  error: string | null;
};

type FakeProfileResponse = {
  candidate_id: string;
  candidate: CandidateSummary;
  trust_score: number;
  risk_level: RiskLevel;
  reasoning_bullets: string[];
  score_breakdown: SignalBreakdown[];
  github_check: GitHubCheck;
  cached: boolean;
  computed_at: string;
};

const SIGNAL_LABEL: Record<string, string> = {
  employment_gap: "Employment gap",
  overlap: "Overlapping employment",
  duplicate_contact: "Duplicate contact (email/phone)",
  completeness: "Suspicious completeness",
  timeline_inconsistency: "Timeline consistency",
};

export default function Page() {
  const [candidateId, setCandidateId] = useState("");
  const [ghOverride, setGhOverride] = useState("");
  const [skipGh, setSkipGh] = useState(false);
  const [forceRecompute, setForceRecompute] = useState(false);

  const [data, setData] = useState<FakeProfileResponse | null>(null);
  const [meta, setMeta] = useState<{ status: number; ms: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!candidateId.trim()) {
      setError("Provide a candidate id.");
      return;
    }
    setPending(true);
    setError(null);
    setData(null);
    setMeta(null);
    try {
      const res: ApiResult = await callJson("/api/v1/fake-profile/score", "POST", {
        candidate_id: candidateId.trim(),
        force_recompute: forceRecompute,
        github_username: ghOverride.trim() || undefined,
        skip_github: skipGh,
      });
      setMeta({ status: res.status, ms: Math.round(res.durationMs) });
      if (!res.ok) {
        setError(typeof res.body === "string" ? res.body : JSON.stringify(res.body, null, 2));
        return;
      }
      setData(res.body as FakeProfileResponse);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setPending(false);
    }
  };

  return (
    <main>
      <div className="crumbs"><Link href="/">← Home</Link></div>
      <h1>Fake Profile Detector</h1>
      <p className="lede">
        Anomaly detection on parsed candidate data: 5 internal consistency
        signals plus a GitHub cross-check. Trust score is 100 minus the sum of
        per-signal penalties (each capped). LinkedIn / Aadhaar / Onfido are
        intentionally not part of this flow — see the planning notes.
      </p>

      <form className="tester" onSubmit={submit}>
        <div>
          <label>Candidate id (UUID)</label>
          <input type="text" value={candidateId} onChange={(e) => setCandidateId(e.target.value)} />
        </div>
        <div>
          <label>GitHub username override (optional)</label>
          <input type="text" value={ghOverride} placeholder="alice-lee" onChange={(e) => setGhOverride(e.target.value)} />
        </div>
        <div style={{ display: "flex", gap: 16, fontSize: 12 }}>
          <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <input type="checkbox" checked={skipGh} onChange={(e) => setSkipGh(e.target.checked)} />
            Skip GitHub check
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <input type="checkbox" checked={forceRecompute} onChange={(e) => setForceRecompute(e.target.checked)} />
            Force recompute (bypass cache)
          </label>
        </div>
        <button type="submit" disabled={pending}>{pending ? "Scoring…" : "Score profile"}</button>
      </form>

      {error && (
        <div className="response err">
          <div className="meta">Error</div>
          <pre>{error}</pre>
        </div>
      )}

      {data && (
        <>
          {meta && (
            <p style={{ fontSize: 12, color: "#9ca3af" }}>
              HTTP {meta.status} · {meta.ms} ms · {data.cached ? "served from cache" : "freshly computed"}
            </p>
          )}

          <section style={cardStyle}>
            <h2 style={{ marginTop: 0 }}>Candidate</h2>
            <div style={{ fontWeight: 600, fontSize: 16 }}>{data.candidate.full_name}</div>
            <div style={{ color: "#9ca3af", fontSize: 13 }}>
              {[data.candidate.email, data.candidate.phone, data.candidate.location]
                .filter(Boolean)
                .join(" · ") || "—"}
            </div>
            {data.candidate.headline && (
              <div style={{ marginTop: 6 }}>{data.candidate.headline}</div>
            )}
            <div style={{ marginTop: 8, color: "#9ca3af", fontSize: 12 }}>
              {data.candidate.skill_count} skills · {data.candidate.experience_years} years experience ·{" "}
              {data.candidate.education_count} degrees
            </div>
          </section>

          <section style={cardStyle}>
            <h2 style={{ marginTop: 0 }}>Trust score</h2>
            <div style={{ display: "flex", alignItems: "baseline", gap: 16 }}>
              <div style={{ fontSize: 48, fontFamily: "ui-monospace, monospace", color: scoreColor(data.trust_score) }}>
                {data.trust_score}
              </div>
              <div style={{ color: "#9ca3af" }}>/ 100</div>
              <RiskBadge level={data.risk_level} />
            </div>
          </section>

          <section style={cardStyle}>
            <h2 style={{ marginTop: 0 }}>Why this score</h2>
            <ul style={{ paddingLeft: 20, margin: 0 }}>
              {data.reasoning_bullets.map((b, i) => (
                <li key={i} style={{ marginBottom: 6 }}>{b}</li>
              ))}
            </ul>
          </section>

          <section style={cardStyle}>
            <h2 style={{ marginTop: 0 }}>Signal breakdown</h2>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ color: "#9ca3af", textAlign: "left" }}>
                  <th style={th}>Signal</th>
                  <th style={th}>Result</th>
                  <th style={th}>Penalty</th>
                  <th style={th}>Message</th>
                </tr>
              </thead>
              <tbody>
                {data.score_breakdown.map((s, i) => (
                  <tr key={i} style={{ borderBottom: "1px solid #1a1d24" }}>
                    <td style={td}>{SIGNAL_LABEL[s.signal] ?? s.signal}</td>
                    <td style={td}>{s.fired ? "✗ fired" : "✓ clean"}</td>
                    <td style={{ ...td, color: s.penalty < 0 ? "#fca5a5" : "#9ca3af", fontFamily: "ui-monospace, monospace" }}>
                      {s.penalty || "—"}
                    </td>
                    <td style={{ ...td, color: "#9ca3af" }}>{s.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section style={cardStyle}>
            <h2 style={{ marginTop: 0 }}>GitHub cross-check</h2>
            {!data.github_check.checked ? (
              <p style={{ color: "#9ca3af", fontSize: 13 }}>
                Not run. {data.github_check.warnings[0] ?? ""}
              </p>
            ) : data.github_check.error ? (
              <p style={{ color: "#fca5a5", fontSize: 13 }}>{data.github_check.error}</p>
            ) : (
              <>
                <div style={{ fontSize: 13 }}>
                  <a href={data.github_check.profile_url ?? "#"} target="_blank" rel="noreferrer">
                    github.com/{data.github_check.username}
                  </a>
                  {" · "}
                  account {Math.floor((data.github_check.account_age_days ?? 0) / 365)}y old ·{" "}
                  {data.github_check.public_repos} repos · {data.github_check.followers} followers
                </div>
                <div style={{ marginTop: 8, fontSize: 13 }}>
                  Top languages: {data.github_check.top_languages.join(", ") || "—"}
                </div>
                {data.github_check.claimed_skills_found_in_repos.length > 0 && (
                  <div style={{ marginTop: 6, fontSize: 13, color: "#86efac" }}>
                    ✓ Confirms: {data.github_check.claimed_skills_found_in_repos.join(", ")}
                  </div>
                )}
                {data.github_check.claimed_skills_missing_in_repos.length > 0 && (
                  <div style={{ marginTop: 4, fontSize: 13, color: "#fca5a5" }}>
                    ⚠ Not seen in repos: {data.github_check.claimed_skills_missing_in_repos.join(", ")}
                  </div>
                )}
                {data.github_check.warnings.map((w, i) => (
                  <div key={i} style={{ marginTop: 4, fontSize: 12, color: "#fde68a" }}>
                    ⚠ {w}
                  </div>
                ))}
              </>
            )}
          </section>
        </>
      )}
    </main>
  );
}

const cardStyle: React.CSSProperties = {
  marginTop: 16,
  background: "#1a1d24",
  border: "1px solid #2a2f3a",
  borderRadius: 6,
  padding: 16,
};
const th: React.CSSProperties = { padding: "8px 6px", borderBottom: "1px solid #2a2f3a" };
const td: React.CSSProperties = { padding: "8px 6px" };

function RiskBadge({ level }: { level: RiskLevel }) {
  const map: Record<RiskLevel, { color: string; label: string }> = {
    low: { color: "#86efac", label: "✓ Low risk" },
    medium: { color: "#fde68a", label: "⚠ Medium risk" },
    high: { color: "#fca5a5", label: "✗ High risk" },
  };
  const v = map[level];
  return (
    <span style={{ color: v.color, fontSize: 13, padding: "2px 8px", border: `1px solid ${v.color}`, borderRadius: 4 }}>
      {v.label}
    </span>
  );
}

function scoreColor(score: number): string {
  if (score >= 70) return "#86efac";
  if (score >= 40) return "#fde68a";
  return "#fca5a5";
}

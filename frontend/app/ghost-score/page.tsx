"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { callJson, type ApiResult } from "@/lib/api";

type Job = { id: string; title: string; company: string | null };

type RiskLevel = "active" | "stale" | "likely_ghost";

type Signals = {
  posting_age_days: number;
  days_since_last_activity: number;
  repost_count: number;
  match_scores_count: number;
  days_since_last_interaction: number | null;
  job_status: string;
};

type Breakdown = {
  signal: string;
  fired: boolean;
  penalty: number;
  message: string;
  details: Record<string, unknown>;
};

type Response = {
  job_id: string;
  job_title: string;
  ghost_score: number;
  risk_classification: RiskLevel;
  signals: Signals;
  breakdown: Breakdown[];
  cached: boolean;
  computed_at: string;
};

const SIGNAL_LABEL: Record<string, string> = {
  posting_age: "Posting age",
  last_activity: "Recruiter activity",
  repost_count: "Repost frequency",
  zero_interaction: "Candidate interaction",
  stale_interaction: "Recent candidate scoring",
};

export default function Page() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [jobId, setJobId] = useState("");
  const [force, setForce] = useState(false);
  const [data, setData] = useState<Response | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const res = await callJson("/api/v1/jobs?limit=200", "GET");
        if (res.ok) {
          const list = (res.body as Job[]) ?? [];
          setJobs(list);
          if (list.length > 0) setJobId(list[0].id);
        }
      } catch { /* manual entry fallback */ }
    })();
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!jobId.trim()) {
      setError("Pick or paste a job id.");
      return;
    }
    setPending(true);
    setError(null);
    setData(null);
    try {
      const res: ApiResult = await callJson("/api/v1/jobs/ghost-score", "POST", {
        job_id: jobId.trim(),
        force_recompute: force,
      });
      if (!res.ok) {
        setError(`HTTP ${res.status}: ${JSON.stringify(res.body)}`);
        return;
      }
      setData(res.body as Response);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setPending(false);
    }
  };

  return (
    <main>
      <div className="crumbs"><Link href="/">← Home</Link></div>
      <h1>Ghost Job Detector</h1>
      <p className="lede">
        Scores how likely a posting is &ldquo;ghost&rdquo; — still marked open
        but with no real hiring activity. Higher score = more ghost-like.
        Cache rots with time; tick <em>Force recompute</em> for current data.
      </p>

      <form className="tester" onSubmit={submit}>
        <div>
          <label>Job</label>
          {jobs.length > 0 ? (
            <select value={jobId} onChange={(e) => setJobId(e.target.value)} style={selectStyle}>
              {jobs.map((j) => (
                <option key={j.id} value={j.id}>
                  {j.title}{j.company ? ` — ${j.company}` : ""}
                </option>
              ))}
            </select>
          ) : (
            <input type="text" value={jobId} onChange={(e) => setJobId(e.target.value)} placeholder="Paste a job UUID" />
          )}
        </div>
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12 }}>
          <input type="checkbox" checked={force} onChange={(e) => setForce(e.target.checked)} />
          Force recompute (bypass cache)
        </label>
        <button type="submit" disabled={pending}>{pending ? "Scoring…" : "Score"}</button>
      </form>

      {error && <div className="response err"><pre>{error}</pre></div>}

      {data && (
        <>
          <section style={cardStyle}>
            <h2 style={{ marginTop: 0 }}>{data.job_title}</h2>
            <div style={{ color: "#9ca3af", fontSize: 12 }}>
              {data.cached ? "served from cache" : "freshly computed"}
            </div>
          </section>

          <section style={cardStyle}>
            <h2 style={{ marginTop: 0 }}>Ghost score</h2>
            <div style={{ display: "flex", alignItems: "baseline", gap: 16 }}>
              <div style={{ fontSize: 48, fontFamily: "ui-monospace, monospace", color: ghostColor(data.ghost_score) }}>
                {data.ghost_score}
              </div>
              <div style={{ color: "#9ca3af" }}>/ 100</div>
              <RiskBadge level={data.risk_classification} />
            </div>
          </section>

          <section style={cardStyle}>
            <h2 style={{ marginTop: 0 }}>Raw signals</h2>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <tbody>
                <Row label="Posting age" value={`${data.signals.posting_age_days} days`} />
                <Row label="Days since last recruiter activity" value={`${data.signals.days_since_last_activity} days`} />
                <Row label="Repost count" value={`${data.signals.repost_count}`} />
                <Row label="Candidates scored against this job" value={`${data.signals.match_scores_count}`} />
                <Row
                  label="Days since last candidate scoring"
                  value={data.signals.days_since_last_interaction === null ? "never" : `${data.signals.days_since_last_interaction} days`}
                />
                <Row label="Job status" value={data.signals.job_status} />
              </tbody>
            </table>
          </section>

          <section style={cardStyle}>
            <h2 style={{ marginTop: 0 }}>Signal breakdown</h2>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ color: "#9ca3af", textAlign: "left" }}>
                  <th style={th}>Signal</th>
                  <th style={th}>Result</th>
                  <th style={th}>+Score</th>
                  <th style={th}>Detail</th>
                </tr>
              </thead>
              <tbody>
                {data.breakdown.map((b, i) => (
                  <tr key={i} style={{ borderBottom: "1px solid #1a1d24" }}>
                    <td style={td}>{SIGNAL_LABEL[b.signal] ?? b.signal}</td>
                    <td style={td}>{b.fired ? "✗ fired" : "✓ clean"}</td>
                    <td style={{ ...td, color: b.penalty > 0 ? "#fca5a5" : "#9ca3af", fontFamily: "ui-monospace, monospace" }}>
                      {b.penalty || "—"}
                    </td>
                    <td style={{ ...td, color: "#9ca3af" }}>{b.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
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
const selectStyle: React.CSSProperties = {
  width: "100%",
  background: "#0b0d12",
  border: "1px solid #2a2f3a",
  color: "#e6e6e6",
  padding: "10px 12px",
  borderRadius: 6,
  fontFamily: "ui-monospace, monospace",
  fontSize: 13,
};

function Row({ label, value }: { label: string; value: string }) {
  return (
    <tr style={{ borderBottom: "1px solid #1a1d24" }}>
      <td style={{ ...td, color: "#9ca3af" }}>{label}</td>
      <td style={{ ...td, fontFamily: "ui-monospace, monospace" }}>{value}</td>
    </tr>
  );
}

function RiskBadge({ level }: { level: RiskLevel }) {
  const map: Record<RiskLevel, { color: string; label: string }> = {
    active: { color: "#86efac", label: "✓ Active" },
    stale: { color: "#fde68a", label: "⚠ Stale" },
    likely_ghost: { color: "#fca5a5", label: "✗ Likely ghost" },
  };
  const v = map[level];
  return (
    <span style={{ color: v.color, fontSize: 13, padding: "2px 8px", border: `1px solid ${v.color}`, borderRadius: 4 }}>
      {v.label}
    </span>
  );
}

function ghostColor(score: number): string {
  if (score >= 60) return "#fca5a5";
  if (score >= 30) return "#fde68a";
  return "#86efac";
}

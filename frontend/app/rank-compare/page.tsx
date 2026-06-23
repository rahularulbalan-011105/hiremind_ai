"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { callJson, type ApiResult } from "@/lib/api";

type Job = { id: string; title: string; company: string | null };

type Components = {
  match_score: number;
  hiring_probability: number;
  trust_score: number;
  experience_score: number;
};

type Hit = {
  rank: number;
  candidate_id: string;
  full_name: string;
  headline: string | null;
  location: string | null;
  final_score: number;
  components: Components;
  candidate_years: number;
  fake_profile_risk: "low" | "medium" | "high" | "unknown";
  hiring_probability_raw: number;
  hiring_model_type: "xgboost" | "rules" | null;
  match_summary: string;
};

type Response = {
  job_id: string;
  job_title: string;
  weights_used: Record<string, number>;
  hits: Hit[];
  computed_at: string;
};

export default function Page() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [jobId, setJobId] = useState("");
  const [candidateCsv, setCandidateCsv] = useState("");
  const [wMatch, setWMatch] = useState(0.45);
  const [wHiring, setWHiring] = useState(0.30);
  const [wTrust, setWTrust] = useState(0.15);
  const [wExp, setWExp] = useState(0.10);
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
      } catch { /* manual entry */ }
    })();
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const ids = candidateCsv.split(/[\s,]+/).map((s) => s.trim()).filter(Boolean);
    if (!jobId.trim() || ids.length === 0) {
      setError("Pick a job and paste at least one candidate UUID.");
      return;
    }
    setPending(true);
    setError(null);
    setData(null);
    try {
      const res: ApiResult = await callJson("/api/v1/rank/compare", "POST", {
        job_id: jobId.trim(),
        candidate_ids: ids,
        weights: {
          match: wMatch,
          hiring_probability: wHiring,
          trust: wTrust,
          experience: wExp,
        },
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
      <h1>Candidate Comparison</h1>
      <p className="lede">
        Side-by-side comparison of a hand-picked set of candidates against one
        job. Rows preserve input order — no sorting. For a fully-sorted ranked
        list, use <Link href="/rank">Rank</Link>.
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

        <div>
          <label>Candidate UUIDs (one per line or comma-separated)</label>
          <textarea
            value={candidateCsv}
            onChange={(e) => setCandidateCsv(e.target.value)}
            placeholder={"9b8d6f0a-...\nabcdef01-..."}
            style={{ minHeight: 120 }}
          />
        </div>

        <div>
          <label>Weights</label>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(110px, 1fr))", gap: 10 }}>
            <WeightField label="Match" value={wMatch} setValue={setWMatch} />
            <WeightField label="Hiring Prob" value={wHiring} setValue={setWHiring} />
            <WeightField label="Trust" value={wTrust} setValue={setWTrust} />
            <WeightField label="Experience" value={wExp} setValue={setWExp} />
          </div>
        </div>

        <button type="submit" disabled={pending}>{pending ? "Comparing…" : "Compare"}</button>
      </form>

      {error && <div className="response err"><pre>{error}</pre></div>}

      {data && (
        <>
          <h2>vs {data.job_title}</h2>
          {data.hits.length === 0 ? (
            <p style={{ color: "#9ca3af" }}>No candidates returned.</p>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: `repeat(${data.hits.length}, minmax(220px, 1fr))`, gap: 12, overflowX: "auto" }}>
              {data.hits.map((h) => (
                <div key={h.candidate_id} style={cardStyle}>
                  <div style={{ fontWeight: 600, fontSize: 14 }}>{h.full_name}</div>
                  {h.headline && <div style={{ color: "#9ca3af", fontSize: 11, marginBottom: 8 }}>{h.headline}</div>}
                  <div style={{ fontSize: 36, fontFamily: "ui-monospace, monospace", color: scoreColor(h.final_score) }}>
                    {h.final_score}
                  </div>
                  <div style={{ color: "#9ca3af", fontSize: 11, marginBottom: 12 }}>final score</div>

                  <Stat label="Match" value={h.components.match_score} />
                  <Stat label={`Hiring %${h.hiring_model_type ? ` (${h.hiring_model_type})` : ""}`} value={h.components.hiring_probability} />
                  <Stat label="Trust" value={h.components.trust_score} risk={h.fake_profile_risk} />
                  <Stat label={`Exp (${h.candidate_years.toFixed(1)}y)`} value={h.components.experience_score} />

                  <div style={{ marginTop: 12, color: "#9ca3af", fontSize: 11 }}>
                    {h.match_summary}
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </main>
  );
}

const cardStyle: React.CSSProperties = {
  background: "#1a1d24",
  border: "1px solid #2a2f3a",
  borderRadius: 6,
  padding: 14,
};
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

function WeightField({ label, value, setValue }: { label: string; value: number; setValue: (n: number) => void }) {
  return (
    <div>
      <label style={{ fontSize: 10, color: "#9ca3af", textTransform: "uppercase", letterSpacing: "0.04em" }}>
        {label}
      </label>
      <input type="number" step="0.05" min={0} max={1} value={value}
        onChange={(e) => setValue(parseFloat(e.target.value || "0"))}
        style={{ width: "100%" }} />
    </div>
  );
}

function Stat({ label, value, risk }: { label: string; value: number; risk?: Hit["fake_profile_risk"] }) {
  let color = "#e6e6e6";
  if (risk === "low") color = "#86efac";
  else if (risk === "medium") color = "#fde68a";
  else if (risk === "high") color = "#fca5a5";
  else if (risk === "unknown") color = "#6b7280";
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 0", borderBottom: "1px solid #1a1d24" }}>
      <span style={{ color: "#9ca3af", fontSize: 11 }}>{label}</span>
      <span style={{ fontFamily: "ui-monospace, monospace", fontSize: 13, color }}>{value}</span>
    </div>
  );
}

function scoreColor(score: number): string {
  if (score >= 75) return "#86efac";
  if (score >= 50) return "#fde68a";
  if (score >= 25) return "#fdba74";
  return "#fca5a5";
}

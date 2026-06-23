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
  total_candidates_ranked: number;
  top_k: number;
  weights_used: { match: number; hiring_probability: number; trust: number; experience: number };
  hits: Hit[];
  computed_at: string;
};

export default function Page() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [jobId, setJobId] = useState("");
  const [topK, setTopK] = useState(20);
  const [wMatch, setWMatch] = useState(0.45);
  const [wHiring, setWHiring] = useState(0.30);
  const [wTrust, setWTrust] = useState(0.15);
  const [wExp, setWExp] = useState(0.10);
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
      } catch { /* manual entry */ }
    })();
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!jobId.trim()) {
      setError("Pick a job first.");
      return;
    }
    setPending(true);
    setError(null);
    setData(null);
    try {
      const res: ApiResult = await callJson("/api/v1/rank/candidates", "POST", {
        job_id: jobId.trim(),
        top_k: topK,
        weights: {
          match: wMatch,
          hiring_probability: wHiring,
          trust: wTrust,
          experience: wExp,
        },
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

  const totalW = wMatch + wHiring + wTrust + wExp;

  return (
    <main>
      <div className="crumbs"><Link href="/">← Home</Link></div>
      <h1>Candidate Ranker</h1>
      <p className="lede">
        Final composite ranking — combines match score (Module 3) + hiring
        probability (Module 8) + trust score (Module 5) + experience seniority.
        Weights auto-normalize. Need a side-by-side view of specific
        candidates? Go to <Link href="/rank-compare">Compare</Link>.
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
          <label>Weights (auto-normalized; out of {totalW.toFixed(2)})</label>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(110px, 1fr))", gap: 10 }}>
            <WeightField label="Match" value={wMatch} setValue={setWMatch} />
            <WeightField label="Hiring Prob" value={wHiring} setValue={setWHiring} />
            <WeightField label="Trust" value={wTrust} setValue={setWTrust} />
            <WeightField label="Experience" value={wExp} setValue={setWExp} />
          </div>
        </div>

        <div style={{ display: "flex", gap: 16, alignItems: "flex-end" }}>
          <div>
            <label>Top K</label>
            <input
              type="number"
              min={1}
              max={500}
              value={topK}
              onChange={(e) => setTopK(parseInt(e.target.value || "20", 10))}
              style={{ width: 100 }}
            />
          </div>
          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, paddingBottom: 8 }}>
            <input type="checkbox" checked={force} onChange={(e) => setForce(e.target.checked)} />
            Force recompute (skip caches)
          </label>
        </div>

        <button type="submit" disabled={pending || !jobId}>{pending ? "Ranking…" : "Rank candidates"}</button>
      </form>

      {error && <div className="response err"><pre>{error}</pre></div>}

      {data && (
        <>
          <h2>Results — {data.job_title}</h2>
          <p style={{ color: "#9ca3af", fontSize: 12, marginTop: -8 }}>
            {data.hits.length} of {data.total_candidates_ranked} candidates shown.
            Weights — match {data.weights_used.match}, hiring {data.weights_used.hiring_probability},
            trust {data.weights_used.trust}, exp {data.weights_used.experience}.
          </p>

          {data.hits.length === 0 ? (
            <p style={{ color: "#9ca3af" }}>
              No candidates ranked. Parse a resume first on <Link href="/resume-parser">Resume Parser</Link>.
            </p>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr style={{ color: "#9ca3af", textAlign: "left" }}>
                    <th style={th}>#</th>
                    <th style={th}>Candidate</th>
                    <th style={th}>Final</th>
                    <th style={th}>Match</th>
                    <th style={th}>Hiring %</th>
                    <th style={th}>Trust</th>
                    <th style={th}>Exp</th>
                    <th style={th}>Summary</th>
                  </tr>
                </thead>
                <tbody>
                  {data.hits.map((h) => (
                    <tr key={h.candidate_id} style={{ borderBottom: "1px solid #1a1d24" }}>
                      <td style={{ ...td, color: "#9ca3af" }}>{h.rank}</td>
                      <td style={td}>
                        <div style={{ fontWeight: 600 }}>{h.full_name}</div>
                        {h.headline && <div style={{ color: "#9ca3af", fontSize: 11 }}>{h.headline}</div>}
                      </td>
                      <td style={td}>
                        <div style={{ fontFamily: "ui-monospace, monospace", fontSize: 18, color: scoreColor(h.final_score) }}>
                          {h.final_score}
                        </div>
                      </td>
                      <td style={tdMono}>{h.components.match_score}</td>
                      <td style={tdMono}>
                        {h.components.hiring_probability}
                        {h.hiring_model_type && (
                          <span style={{ fontSize: 9, color: "#6b7280", marginLeft: 4 }}>
                            ({h.hiring_model_type})
                          </span>
                        )}
                      </td>
                      <td style={tdMono}>
                        <TrustBadge risk={h.fake_profile_risk} score={h.components.trust_score} />
                      </td>
                      <td style={tdMono}>
                        {h.components.experience_score}
                        <span style={{ fontSize: 9, color: "#6b7280", marginLeft: 4 }}>
                          ({h.candidate_years.toFixed(1)}y)
                        </span>
                      </td>
                      <td style={{ ...td, color: "#9ca3af", fontSize: 11 }}>{h.match_summary}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </main>
  );
}

const th: React.CSSProperties = { padding: "8px 6px", borderBottom: "1px solid #2a2f3a" };
const td: React.CSSProperties = { padding: "8px 6px" };
const tdMono: React.CSSProperties = { ...td, fontFamily: "ui-monospace, monospace" };
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
      <input
        type="number" step="0.05" min={0} max={1} value={value}
        onChange={(e) => setValue(parseFloat(e.target.value || "0"))}
        style={{ width: "100%" }}
      />
    </div>
  );
}

function TrustBadge({ risk, score }: { risk: Hit["fake_profile_risk"]; score: number }) {
  if (risk === "unknown") {
    return <span style={{ color: "#6b7280", fontSize: 11 }}>not scored</span>;
  }
  const map = {
    low: { color: "#86efac", label: `✓ ${score}` },
    medium: { color: "#fde68a", label: `⚠ ${score}` },
    high: { color: "#fca5a5", label: `✗ ${score}` },
  } as const;
  const v = map[risk];
  return <span style={{ color: v.color }}>{v.label}</span>;
}

function scoreColor(score: number): string {
  if (score >= 75) return "#86efac";
  if (score >= 50) return "#fde68a";
  if (score >= 25) return "#fdba74";
  return "#fca5a5";
}

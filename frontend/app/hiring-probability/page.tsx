"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { callJson, type ApiResult } from "@/lib/api";

type Job = { id: string; title: string; company: string | null };

type FeatureContribution = { feature: string; contribution: number };

type Response = {
  candidate_id: string;
  job_id: string;
  probability: number;
  confidence: number;
  model_version: string;
  model_type: "xgboost" | "rules";
  features_used: Record<string, number>;
  shap_explanations: FeatureContribution[];
  cached: boolean;
  computed_at: string;
};

const FEATURE_LABEL: Record<string, string> = {
  semantic_score: "Semantic match",
  skill_overlap_score: "Skill overlap",
  experience_score: "Experience fit",
  location_score: "Location fit",
  notice_period_score: "Notice period",
  salary_score: "Salary fit",
  trust_score: "Trust / fake-profile",
  candidate_years: "Years of experience",
  required_years_gap: "Years vs. requirement (gap)",
  meets_all_required_skills: "Meets all required skills",
  github_verified_skills: "GitHub-verified skills",
};

export default function Page() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [candidateId, setCandidateId] = useState("");
  const [jobId, setJobId] = useState("");
  const [force, setForce] = useState(false);
  const [includeShap, setIncludeShap] = useState(true);
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
    if (!candidateId.trim() || !jobId.trim()) {
      setError("Both candidate id and job id are required.");
      return;
    }
    setPending(true);
    setError(null);
    setData(null);
    try {
      const res: ApiResult = await callJson("/api/v1/hiring-probability/predict", "POST", {
        candidate_id: candidateId.trim(),
        job_id: jobId.trim(),
        force_recompute: force,
        include_shap: includeShap,
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

  const maxAbsContrib = data?.shap_explanations.length
    ? Math.max(...data.shap_explanations.map((c) => Math.abs(c.contribution)), 0.0001)
    : 1;

  return (
    <main>
      <div className="crumbs"><Link href="/">← Home</Link></div>
      <h1>Hiring Probability Predictor</h1>
      <p className="lede">
        Predicts the probability that the candidate gets hired for the job.
        Backed by XGBoost when a trained model is present in the registry,
        otherwise an always-works rules-based predictor with rule-derived SHAP.
        Train a model via <code>python -m scripts.train_model</code>.
      </p>

      <form className="tester" onSubmit={submit}>
        <div>
          <label>Candidate id (UUID)</label>
          <input type="text" value={candidateId} onChange={(e) => setCandidateId(e.target.value)} />
        </div>
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
        <div style={{ display: "flex", gap: 16, fontSize: 12 }}>
          <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <input type="checkbox" checked={includeShap} onChange={(e) => setIncludeShap(e.target.checked)} />
            Include SHAP explanations
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <input type="checkbox" checked={force} onChange={(e) => setForce(e.target.checked)} />
            Force recompute
          </label>
        </div>
        <button type="submit" disabled={pending}>{pending ? "Predicting…" : "Predict"}</button>
      </form>

      {error && <div className="response err"><pre>{error}</pre></div>}

      {data && (
        <>
          <section style={cardStyle}>
            <h2 style={{ marginTop: 0 }}>Probability of being hired</h2>
            <div style={{ display: "flex", alignItems: "baseline", gap: 16 }}>
              <div style={{ fontSize: 56, fontFamily: "ui-monospace, monospace", color: probColor(data.probability) }}>
                {(data.probability * 100).toFixed(1)}%
              </div>
              <div style={{ color: "#9ca3af" }}>
                confidence {(data.confidence * 100).toFixed(0)}%
              </div>
            </div>
            <ProgressBar value={data.probability} />
            <div style={{ marginTop: 12, color: "#9ca3af", fontSize: 12 }}>
              Model: <code>{data.model_type}</code> · version <code>{data.model_version}</code> ·{" "}
              {data.cached ? "served from cache" : "freshly computed"}
            </div>
          </section>

          <section style={cardStyle}>
            <h2 style={{ marginTop: 0 }}>Features used</h2>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <tbody>
                {Object.entries(data.features_used).map(([name, val]) => (
                  <tr key={name} style={{ borderBottom: "1px solid #1a1d24" }}>
                    <td style={{ ...td, color: "#9ca3af" }}>{FEATURE_LABEL[name] ?? name}</td>
                    <td style={{ ...td, fontFamily: "ui-monospace, monospace" }}>{val.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          {data.shap_explanations.length > 0 && (
            <section style={cardStyle}>
              <h2 style={{ marginTop: 0 }}>Feature contributions {data.model_type === "xgboost" ? "(SHAP)" : "(rules-derived)"}</h2>
              <p style={{ color: "#9ca3af", fontSize: 12, margin: "0 0 12px" }}>
                Positive = pushes prediction higher (more likely to be hired).
                Negative = pushes lower. Sorted by absolute impact.
              </p>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <tbody>
                  {data.shap_explanations.map((c) => (
                    <tr key={c.feature} style={{ borderBottom: "1px solid #1a1d24" }}>
                      <td style={{ ...td, color: "#9ca3af", width: "30%" }}>{FEATURE_LABEL[c.feature] ?? c.feature}</td>
                      <td style={{ ...td }}>
                        <ContribBar value={c.contribution} maxAbs={maxAbsContrib} />
                      </td>
                      <td style={{ ...td, fontFamily: "ui-monospace, monospace", textAlign: "right", width: 80, color: c.contribution >= 0 ? "#86efac" : "#fca5a5" }}>
                        {c.contribution >= 0 ? "+" : ""}{c.contribution.toFixed(3)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}
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

function ProgressBar({ value }: { value: number }) {
  const pct = Math.max(0, Math.min(100, value * 100));
  return (
    <div style={{ marginTop: 12, height: 10, background: "#0b0d12", border: "1px solid #2a2f3a", borderRadius: 6, overflow: "hidden" }}>
      <div style={{ width: `${pct}%`, height: "100%", background: probColor(value) }} />
    </div>
  );
}

function ContribBar({ value, maxAbs }: { value: number; maxAbs: number }) {
  const widthPct = (Math.abs(value) / maxAbs) * 50; // ±50% around the center
  return (
    <div style={{ position: "relative", height: 14, background: "#0b0d12", border: "1px solid #2a2f3a", borderRadius: 4 }}>
      <div style={{ position: "absolute", top: 0, bottom: 0, left: "50%", width: 1, background: "#3a4150" }} />
      <div
        style={{
          position: "absolute",
          top: 0,
          bottom: 0,
          left: value >= 0 ? "50%" : `${50 - widthPct}%`,
          width: `${widthPct}%`,
          background: value >= 0 ? "#22c55e" : "#ef4444",
          opacity: 0.7,
        }}
      />
    </div>
  );
}

function probColor(p: number): string {
  if (p >= 0.7) return "#86efac";
  if (p >= 0.4) return "#fde68a";
  return "#fca5a5";
}

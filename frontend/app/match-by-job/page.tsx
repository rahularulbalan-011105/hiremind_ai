"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { callJson, type ApiResult } from "@/lib/api";

type Job = {
  id: string;
  title: string;
  company: string | null;
  location: string | null;
  status: string;
  required_skills: string[];
  required_years_experience: number | null;
  embedding_stored: boolean;
};

type Subscores = {
  semantic: number;
  skill_overlap: number;
  experience: number;
  location: number;
  notice_period: number;
  salary: number;
};

type DuplicateRef = {
  candidate_id: string;
  full_name: string;
  similarity: number;
  kind: "hard" | "likely" | "similar";
};

type Hit = {
  candidate_id: string;
  full_name: string;
  headline: string | null;
  location: string | null;
  match_score: number;
  subscores: Subscores;
  matched_skills: string[];
  missing_skills: string[];
  candidate_years: number;
  summary: string;
  fake_profile_risk: "low" | "medium" | "high" | "unknown";
  trust_score: number | null;
  possible_duplicates: DuplicateRef[];
};

type MatchByJobResponse = {
  job_id: string;
  job_title: string;
  total_candidates_scored: number;
  top_k: number;
  weights_used: {
    semantic: number;
    skill_overlap: number;
    experience: number;
    location: number;
    notice_period: number;
    salary: number;
  };
  hits: Hit[];
};

export default function Page() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string>("");
  const [jobsError, setJobsError] = useState<string | null>(null);

  const [topK, setTopK] = useState(20);
  const [wSemantic, setWSemantic] = useState(0.25);
  const [wSkill, setWSkill] = useState(0.25);
  const [wExp, setWExp] = useState(0.15);
  const [wLocation, setWLocation] = useState(0.10);
  const [wNotice, setWNotice] = useState(0.10);
  const [wSalary, setWSalary] = useState(0.15);

  const [result, setResult] = useState<MatchByJobResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  // Fetch jobs on load
  useEffect(() => {
    (async () => {
      try {
        const res = await callJson("/api/v1/jobs?limit=200", "GET");
        if (!res.ok) {
          setJobsError(`Failed to load jobs: HTTP ${res.status}`);
          return;
        }
        const list = (res.body as Job[]) ?? [];
        setJobs(list);
        if (list.length > 0) setSelectedJobId(list[0].id);
      } catch (err) {
        setJobsError((err as Error).message);
      }
    })();
  }, []);

  const run = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedJobId) {
      setError("Pick a job first.");
      return;
    }
    setPending(true);
    setError(null);
    setResult(null);
    try {
      const res = await callJson("/api/v1/match/by-job", "POST", {
        job_id: selectedJobId,
        top_k: topK,
        weights: {
          semantic: wSemantic,
          skill_overlap: wSkill,
          experience: wExp,
          location: wLocation,
          notice_period: wNotice,
          salary: wSalary,
        },
      });
      if (!res.ok) {
        setError(`HTTP ${res.status}: ${JSON.stringify(res.body)}`);
        return;
      }
      setResult(res.body as MatchByJobResponse);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setPending(false);
    }
  };

  const selectedJob = jobs.find((j) => j.id === selectedJobId);

  return (
    <main>
      <div className="crumbs"><Link href="/">← Home</Link></div>
      <h1>Match by Job (Recruiter view)</h1>
      <p className="lede">
        Pick one of your jobs from the dropdown, then score every candidate that
        has a parsed resume. Ranked by composite match score (semantic + skill
        overlap + experience). Click a candidate row to drill into the full
        LLM-generated reasoning on the single-pair <Link href="/match">Match</Link> page.
      </p>

      <form className="tester" onSubmit={run}>
        <div>
          <label>Job</label>
          {jobsError && <pre style={{ color: "#fecaca" }}>{jobsError}</pre>}
          {jobs.length === 0 && !jobsError ? (
            <p style={{ color: "#9ca3af", fontSize: 13 }}>
              No jobs yet. Create one on <Link href="/jobs-create">Create Job</Link>.
            </p>
          ) : (
            <select
              value={selectedJobId}
              onChange={(e) => setSelectedJobId(e.target.value)}
              style={{
                width: "100%",
                background: "#0b0d12",
                border: "1px solid #2a2f3a",
                color: "#e6e6e6",
                padding: "10px 12px",
                borderRadius: 6,
                fontFamily: "ui-monospace, monospace",
                fontSize: 13,
              }}
            >
              {jobs.map((j) => (
                <option key={j.id} value={j.id}>
                  {j.title}
                  {j.company ? ` — ${j.company}` : ""}
                  {j.embedding_stored ? "" : " ⚠ no embedding"}
                </option>
              ))}
            </select>
          )}
        </div>

        {selectedJob && (
          <div style={{ fontSize: 12, color: "#9ca3af" }}>
            <div>Required skills: {selectedJob.required_skills.join(", ") || "—"}</div>
            <div>Required years: {selectedJob.required_years_experience ?? "—"}</div>
            <div>Embedding stored: {selectedJob.embedding_stored ? "yes" : "no — re-create the job"}</div>
          </div>
        )}

        <div>
          <label>Weights (auto-normalized; out of {(wSemantic + wSkill + wExp + wLocation + wNotice + wSalary).toFixed(2)})</label>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(110px, 1fr))", gap: 10 }}>
            <WeightField label="Semantic" value={wSemantic} setValue={setWSemantic} />
            <WeightField label="Skill" value={wSkill} setValue={setWSkill} />
            <WeightField label="Experience" value={wExp} setValue={setWExp} />
            <WeightField label="Location" value={wLocation} setValue={setWLocation} />
            <WeightField label="Notice" value={wNotice} setValue={setWNotice} />
            <WeightField label="Salary" value={wSalary} setValue={setWSalary} />
          </div>
        </div>
        <div>
          <label>Top K</label>
          <input
            type="number"
            value={topK}
            min={1}
            max={500}
            onChange={(e) => setTopK(parseInt(e.target.value || "20", 10))}
            style={{ width: 100 }}
          />
        </div>

        <button type="submit" disabled={pending || !selectedJobId}>
          {pending ? "Scoring…" : "Score all candidates"}
        </button>
      </form>

      {error && (
        <div className="response err">
          <div className="meta">Error</div>
          <pre>{error}</pre>
        </div>
      )}

      {result && (
        <>
          <h2>Results — {result.job_title}</h2>
          <p style={{ color: "#9ca3af", fontSize: 12, marginTop: -8 }}>
            {result.hits.length} of {result.total_candidates_scored} candidates shown.
            Weights — sem {result.weights_used.semantic}, skill {result.weights_used.skill_overlap}, exp {result.weights_used.experience},
            loc {result.weights_used.location}, notice {result.weights_used.notice_period}, salary {result.weights_used.salary}.
          </p>

          {result.hits.length === 0 ? (
            <p style={{ color: "#9ca3af" }}>
              No candidates with embeddings yet. Parse a resume on <Link href="/resume-parser">Resume Parser</Link>.
            </p>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr style={{ color: "#9ca3af", textAlign: "left" }}>
                    <th style={{ padding: "8px 6px", borderBottom: "1px solid #2a2f3a" }}>#</th>
                    <th style={{ padding: "8px 6px", borderBottom: "1px solid #2a2f3a" }}>Name</th>
                    <th style={{ padding: "8px 6px", borderBottom: "1px solid #2a2f3a" }}>Score</th>
                    <th style={{ padding: "8px 6px", borderBottom: "1px solid #2a2f3a" }} title="Semantic / Skill / Experience / Location / Notice / Salary">
                      Sub (Sem/Sk/Exp/Loc/Not/Sal)
                    </th>
                    <th style={{ padding: "8px 6px", borderBottom: "1px solid #2a2f3a" }}>Trust</th>
                    <th style={{ padding: "8px 6px", borderBottom: "1px solid #2a2f3a" }}>Matched</th>
                    <th style={{ padding: "8px 6px", borderBottom: "1px solid #2a2f3a" }}>Missing</th>
                    <th style={{ padding: "8px 6px", borderBottom: "1px solid #2a2f3a" }}>Duplicates</th>
                  </tr>
                </thead>
                <tbody>
                  {result.hits.map((h, i) => (
                    <tr key={h.candidate_id} style={{ borderBottom: "1px solid #1a1d24" }}>
                      <td style={{ padding: "8px 6px", color: "#9ca3af" }}>{i + 1}</td>
                      <td style={{ padding: "8px 6px" }}>
                        <div style={{ fontWeight: 600 }}>{h.full_name}</div>
                        {h.headline && <div style={{ color: "#9ca3af", fontSize: 11 }}>{h.headline}</div>}
                      </td>
                      <td style={{ padding: "8px 6px" }}>
                        <div style={{ fontFamily: "ui-monospace, monospace", fontSize: 16, color: scoreColor(h.match_score) }}>
                          {h.match_score}
                        </div>
                      </td>
                      <td style={{ padding: "8px 6px", fontFamily: "ui-monospace, monospace", fontSize: 11, color: "#9ca3af" }}>
                        {h.subscores.semantic.toFixed(0)} / {h.subscores.skill_overlap.toFixed(0)} / {h.subscores.experience.toFixed(0)}{" "}
                        / {h.subscores.location.toFixed(0)} / {h.subscores.notice_period.toFixed(0)} / {h.subscores.salary.toFixed(0)}
                      </td>
                      <td style={{ padding: "8px 6px", fontSize: 11 }}>
                        <TrustBadge risk={h.fake_profile_risk} score={h.trust_score} />
                      </td>
                      <td style={{ padding: "8px 6px", fontSize: 11, color: "#86efac" }}>
                        {h.matched_skills.length > 0 ? h.matched_skills.slice(0, 4).join(", ") : "—"}
                      </td>
                      <td style={{ padding: "8px 6px", fontSize: 11, color: "#fca5a5" }}>
                        {h.missing_skills.length > 0 ? h.missing_skills.slice(0, 4).join(", ") : "—"}
                      </td>
                      <td style={{ padding: "8px 6px", fontSize: 11 }}>
                        {h.possible_duplicates.length === 0 ? (
                          <span style={{ color: "#9ca3af" }}>—</span>
                        ) : (
                          h.possible_duplicates.slice(0, 2).map((d, di) => (
                            <div key={di} style={{ color: dupColor(d.kind) }}>
                              {dupIcon(d.kind)} {d.full_name} ({(d.similarity * 100).toFixed(0)}%)
                            </div>
                          ))
                        )}
                      </td>
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

function scoreColor(score: number): string {
  if (score >= 75) return "#86efac";
  if (score >= 50) return "#fde68a";
  if (score >= 25) return "#fdba74";
  return "#fca5a5";
}

function TrustBadge({ risk, score }: { risk: Hit["fake_profile_risk"]; score: number | null }) {
  if (risk === "unknown" || score === null) {
    return <span style={{ color: "#6b7280" }}>not scored</span>;
  }
  const map = {
    low: { color: "#86efac", label: `✓ ${score}` },
    medium: { color: "#fde68a", label: `⚠ ${score}` },
    high: { color: "#fca5a5", label: `✗ ${score}` },
  } as const;
  const v = map[risk];
  return <span style={{ color: v.color, fontFamily: "ui-monospace, monospace" }}>{v.label}</span>;
}

function dupColor(kind: DuplicateRef["kind"]): string {
  if (kind === "hard") return "#fca5a5";
  if (kind === "likely") return "#fdba74";
  return "#fde68a";
}
function dupIcon(kind: DuplicateRef["kind"]): string {
  if (kind === "hard") return "✗";
  if (kind === "likely") return "⚠";
  return "≈";
}

function WeightField({
  label,
  value,
  setValue,
}: {
  label: string;
  value: number;
  setValue: (n: number) => void;
}) {
  return (
    <div>
      <label style={{ fontSize: 10, color: "#9ca3af", textTransform: "uppercase", letterSpacing: "0.04em" }}>
        {label}
      </label>
      <input
        type="number"
        step="0.05"
        min={0}
        max={1}
        value={value}
        onChange={(e) => setValue(parseFloat(e.target.value || "0"))}
        style={{ width: "100%" }}
      />
    </div>
  );
}

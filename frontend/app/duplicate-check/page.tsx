"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { callJson, type ApiResult } from "@/lib/api";

type Job = {
  id: string;
  title: string;
  company: string | null;
  embedding_stored: boolean;
};

type Verdict = "hard" | "likely" | "similar";

type DuplicateMatch = {
  duplicate_job_id: string;
  title: string;
  company: string | null;
  title_similarity: number;
  embedding_similarity: number;
  shared_required_skills: string[];
  same_company: boolean;
  verdict: Verdict;
};

type Response = {
  job_id: string;
  job_title: string;
  total_compared: number;
  duplicates: DuplicateMatch[];
  cached: boolean;
  computed_at: string;
};

export default function Page() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [jobId, setJobId] = useState("");
  const [maxCandidates, setMaxCandidates] = useState(50);
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
      } catch { /* swallow — manual id entry still works */ }
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
      const res: ApiResult = await callJson("/api/v1/jobs/duplicate-check", "POST", {
        job_id: jobId.trim(),
        force_recompute: force,
        max_candidates: maxCandidates,
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
      <h1>Duplicate Job Detector</h1>
      <p className="lede">
        Combines RapidFuzz title similarity + JD embedding cosine + same-company
        signal. Same-company duplicates are caught at a lower bar than
        cross-company near-matches (which are usually just market overlap).
      </p>

      <form className="tester" onSubmit={submit}>
        <div>
          <label>Job</label>
          {jobs.length > 0 ? (
            <select
              value={jobId}
              onChange={(e) => setJobId(e.target.value)}
              style={selectStyle}
            >
              {jobs.map((j) => (
                <option key={j.id} value={j.id}>
                  {j.title}{j.company ? ` — ${j.company}` : ""}{j.embedding_stored ? "" : " ⚠ no embedding"}
                </option>
              ))}
            </select>
          ) : (
            <input
              type="text"
              value={jobId}
              onChange={(e) => setJobId(e.target.value)}
              placeholder="Paste a job UUID"
            />
          )}
        </div>
        <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
          <div>
            <label>HNSW pre-filter (max candidates)</label>
            <input
              type="number"
              min={1}
              max={200}
              value={maxCandidates}
              onChange={(e) => setMaxCandidates(parseInt(e.target.value || "50", 10))}
              style={{ width: 100 }}
            />
          </div>
          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12 }}>
            <input type="checkbox" checked={force} onChange={(e) => setForce(e.target.checked)} />
            Force recompute
          </label>
        </div>
        <button type="submit" disabled={pending}>{pending ? "Checking…" : "Find duplicates"}</button>
      </form>

      {error && (
        <div className="response err"><pre>{error}</pre></div>
      )}

      {data && (
        <>
          <section style={cardStyle}>
            <h2 style={{ marginTop: 0 }}>{data.job_title}</h2>
            <div style={{ color: "#9ca3af", fontSize: 13 }}>
              Compared against {data.total_compared} nearest job(s) ·{" "}
              {data.duplicates.length} duplicate(s) found ·{" "}
              {data.cached ? "cached" : "freshly computed"}
            </div>
          </section>

          {data.duplicates.length === 0 ? (
            <p style={{ color: "#9ca3af", marginTop: 16 }}>
              No duplicates above threshold. This job is unique among the {data.total_compared} nearest in the database.
            </p>
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13, marginTop: 16 }}>
              <thead>
                <tr style={{ color: "#9ca3af", textAlign: "left" }}>
                  <th style={th}>Verdict</th>
                  <th style={th}>Title</th>
                  <th style={th}>Company</th>
                  <th style={th}>Title sim</th>
                  <th style={th}>JD sim</th>
                  <th style={th}>Shared skills</th>
                </tr>
              </thead>
              <tbody>
                {data.duplicates.map((d) => (
                  <tr key={d.duplicate_job_id} style={{ borderBottom: "1px solid #1a1d24" }}>
                    <td style={td}><VerdictBadge v={d.verdict} same={d.same_company} /></td>
                    <td style={td}>{d.title}</td>
                    <td style={td}>{d.company ?? "—"}</td>
                    <td style={{ ...td, fontFamily: "ui-monospace, monospace" }}>{(d.title_similarity * 100).toFixed(0)}%</td>
                    <td style={{ ...td, fontFamily: "ui-monospace, monospace" }}>{(d.embedding_similarity * 100).toFixed(0)}%</td>
                    <td style={{ ...td, color: "#9ca3af", fontSize: 11 }}>
                      {d.shared_required_skills.length > 0 ? d.shared_required_skills.join(", ") : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
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

function VerdictBadge({ v, same }: { v: Verdict; same: boolean }) {
  const map = {
    hard: { color: "#fca5a5", label: "✗ Hard" },
    likely: { color: "#fdba74", label: "⚠ Likely" },
    similar: { color: "#fde68a", label: "≈ Similar" },
  } as const;
  const x = map[v];
  return (
    <span style={{ color: x.color, fontFamily: "ui-monospace, monospace" }}>
      {x.label}{same ? " · same co." : ""}
    </span>
  );
}

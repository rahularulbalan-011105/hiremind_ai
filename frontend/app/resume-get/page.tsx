"use client";

import Link from "next/link";
import { useState } from "react";
import { callJson, type ApiResult } from "@/lib/api";

export default function Page() {
  const [candidateId, setCandidateId] = useState("");
  const [result, setResult] = useState<ApiResult | null>(null);
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
    setResult(null);
    try {
      const res = await callJson(`/api/v1/resumes/${encodeURIComponent(candidateId.trim())}`, "GET");
      setResult(res);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setPending(false);
    }
  };

  return (
    <main>
      <div className="crumbs"><Link href="/">← Home</Link></div>
      <h1>Get Candidate</h1>
      <p className="lede">Fetch a parsed candidate profile by id.</p>

      <form className="tester" onSubmit={submit}>
        <div>
          <label>Candidate id (UUID)</label>
          <input type="text" value={candidateId} onChange={(e) => setCandidateId(e.target.value)} placeholder="e.g. 9b8d6f0a-..." />
        </div>
        <button type="submit" disabled={pending}>{pending ? "Fetching…" : "Fetch"}</button>

        {error && (
          <div className="response err">
            <div className="meta">Client error</div>
            <pre>{error}</pre>
          </div>
        )}
        {result && (
          <div className={`response ${result.ok ? "" : "err"}`}>
            <div className="meta">HTTP {result.status} · {Math.round(result.durationMs)} ms</div>
            <pre>{typeof result.body === "string" ? result.body : JSON.stringify(result.body, null, 2)}</pre>
          </div>
        )}
      </form>
    </main>
  );
}

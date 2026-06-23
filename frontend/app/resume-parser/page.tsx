"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { callJson, callMultipart, type ApiResult } from "@/lib/api";

type ParseJobStatus = "queued" | "running" | "succeeded" | "failed";

type ParseJob = {
  parse_job_id: string;
  status: ParseJobStatus;
  candidate_id: string | null;
  source_url: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
};

export default function Page() {
  const [file, setFile] = useState<File | null>(null);
  const [uploadResult, setUploadResult] = useState<ApiResult | null>(null);
  const [parseJob, setParseJob] = useState<ParseJob | null>(null);
  const [candidate, setCandidate] = useState<ApiResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPoll = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };
  useEffect(() => () => stopPoll(), []);

  const upload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError("Pick a PDF or DOCX first.");
      return;
    }
    stopPoll();
    setError(null);
    setUploadResult(null);
    setParseJob(null);
    setCandidate(null);
    setPending(true);

    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await callMultipart("/api/v1/resumes/parse", fd);
      setUploadResult(res);
      if (!res.ok) {
        setPending(false);
        return;
      }
      const body = res.body as { parse_job_id?: string };
      if (!body?.parse_job_id) {
        setError("Upload accepted but no parse_job_id returned.");
        setPending(false);
        return;
      }
      pollUntilDone(body.parse_job_id);
    } catch (err) {
      setError((err as Error).message);
      setPending(false);
    }
  };

  const pollUntilDone = (jobId: string) => {
    const tick = async () => {
      try {
        const res = await callJson(`/api/v1/resumes/parse-jobs/${jobId}`, "GET");
        if (!res.ok) {
          setError(`Polling failed: HTTP ${res.status}`);
          setPending(false);
          stopPoll();
          return;
        }
        const job = res.body as ParseJob;
        setParseJob(job);
        if (job.status === "succeeded" || job.status === "failed") {
          stopPoll();
          setPending(false);
          if (job.status === "succeeded" && job.candidate_id) {
            const cand = await callJson(`/api/v1/resumes/${job.candidate_id}`, "GET");
            setCandidate(cand);
          }
        }
      } catch (err) {
        setError((err as Error).message);
        setPending(false);
        stopPoll();
      }
    };
    void tick();
    pollRef.current = setInterval(tick, 1500);
  };

  return (
    <main>
      <div className="crumbs"><Link href="/">← Home</Link></div>
      <h1>Resume Parser</h1>
      <p className="lede">
        Upload a PDF or DOCX. Backend returns <code>202 Accepted</code> with a{" "}
        <code>parse_job_id</code>. This page polls every 1.5s until the Celery worker
        finishes, then fetches the parsed candidate profile.
      </p>

      <form className="tester" onSubmit={upload}>
        <div>
          <label>Resume file</label>
          <input
            type="file"
            accept=".pdf,.docx,.doc"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </div>
        <button type="submit" disabled={pending || !file}>
          {pending ? "Working…" : "Upload & parse"}
        </button>
      </form>

      {error && (
        <div className="response err">
          <div className="meta">Client error</div>
          <pre>{error}</pre>
        </div>
      )}

      {uploadResult && (
        <>
          <h2>1. Upload response</h2>
          <div className={`response ${uploadResult.ok ? "" : "err"}`}>
            <div className="meta">HTTP {uploadResult.status} · {Math.round(uploadResult.durationMs)} ms</div>
            <pre>{JSON.stringify(uploadResult.body, null, 2)}</pre>
          </div>
        </>
      )}

      {parseJob && (
        <>
          <h2>2. Parse job ({parseJob.status})</h2>
          <div className={`response ${parseJob.status === "failed" ? "err" : ""}`}>
            <pre>{JSON.stringify(parseJob, null, 2)}</pre>
          </div>
        </>
      )}

      {candidate && (
        <>
          <h2>3. Candidate profile</h2>
          <div className={`response ${candidate.ok ? "" : "err"}`}>
            <div className="meta">HTTP {candidate.status} · {Math.round(candidate.durationMs)} ms</div>
            <pre>{JSON.stringify(candidate.body, null, 2)}</pre>
          </div>
        </>
      )}
    </main>
  );
}

"use client";

import { useState } from "react";
import { callMultipart, type ApiResult } from "@/lib/api";

type Props = {
  path: string;
  fileFieldName?: string;
  accept?: string;
};

export default function FileTester({ path, fileFieldName = "file", accept }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [pathState, setPathState] = useState(path);
  const [result, setResult] = useState<ApiResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError("Pick a file first.");
      return;
    }
    setPending(true);
    setError(null);
    setResult(null);
    try {
      const fd = new FormData();
      fd.append(fileFieldName, file);
      const res = await callMultipart(pathState, fd);
      setResult(res);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setPending(false);
    }
  };

  return (
    <form className="tester" onSubmit={submit}>
      <div>
        <label>Endpoint</label>
        <input type="text" value={`POST ${pathState}`} onChange={(e) => setPathState(e.target.value.replace(/^POST\s+/, ""))} />
      </div>

      <div>
        <label>File ({fileFieldName})</label>
        <input type="file" accept={accept} onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      </div>

      <button type="submit" disabled={pending || !file}>
        {pending ? "Uploading…" : "Upload"}
      </button>

      {error && (
        <div className="response err">
          <div className="meta">Client error</div>
          <pre>{error}</pre>
        </div>
      )}

      {result && (
        <div className={`response ${result.ok ? "" : "err"}`}>
          <div className="meta">
            HTTP {result.status} · {Math.round(result.durationMs)} ms
          </div>
          <pre>{typeof result.body === "string" ? result.body : JSON.stringify(result.body, null, 2)}</pre>
        </div>
      )}
    </form>
  );
}

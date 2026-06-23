"use client";

import { useState } from "react";
import { callJson, type ApiResult } from "@/lib/api";

type Method = "GET" | "POST" | "PUT" | "DELETE";

type Props = {
  method: Method;
  path: string;
  defaultBody?: unknown;
  /** If true, render a textarea for the request body; if false, just a button. */
  withBody?: boolean;
};

export default function JsonTester({ method, path, defaultBody, withBody = true }: Props) {
  const [body, setBody] = useState<string>(
    defaultBody !== undefined ? JSON.stringify(defaultBody, null, 2) : ""
  );
  const [pathState, setPathState] = useState<string>(path);
  const [result, setResult] = useState<ApiResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setPending(true);
    setError(null);
    setResult(null);
    try {
      let parsed: unknown = undefined;
      if (withBody && body.trim()) {
        try {
          parsed = JSON.parse(body);
        } catch (err) {
          setError(`Request body is not valid JSON: ${(err as Error).message}`);
          setPending(false);
          return;
        }
      }
      const res = await callJson(pathState, method, withBody ? parsed : undefined);
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
        <input
          type="text"
          value={`${method} ${pathState}`}
          onChange={(e) => {
            const v = e.target.value.replace(new RegExp(`^${method}\\s+`), "");
            setPathState(v);
          }}
        />
      </div>

      {withBody && (
        <div>
          <label>Request body (JSON)</label>
          <textarea value={body} onChange={(e) => setBody(e.target.value)} spellCheck={false} />
        </div>
      )}

      <button type="submit" disabled={pending}>
        {pending ? "Sending…" : "Send request"}
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

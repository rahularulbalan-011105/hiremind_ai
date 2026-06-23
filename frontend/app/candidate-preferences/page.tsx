"use client";

import Link from "next/link";
import { useState } from "react";
import { callJson, type ApiResult } from "@/lib/api";

type Salary = { min: number; max: number; currency: string };
type Preferences = {
  available_notice_days: number | null;
  expected_salary: Salary | null;
  preferred_locations: string[];
  skill_years: Record<string, number>;
  open_to_remote: boolean;
};

type CandidateProfile = {
  id: string;
  full_name: string;
  email: string | null;
  headline: string | null;
  location: string | null;
  skills: string[];
};

const EMPTY: Preferences = {
  available_notice_days: null,
  expected_salary: null,
  preferred_locations: [],
  skill_years: {},
  open_to_remote: true,
};

export default function Page() {
  const [candidateId, setCandidateId] = useState("");
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [prefs, setPrefs] = useState<Preferences>(EMPTY);

  // Form state
  const [noticeDays, setNoticeDays] = useState<string>("");
  const [salaryMin, setSalaryMin] = useState<string>("");
  const [salaryMax, setSalaryMax] = useState<string>("");
  const [currency, setCurrency] = useState<string>("INR");
  const [locationsCsv, setLocationsCsv] = useState<string>("");
  const [openToRemote, setOpenToRemote] = useState<boolean>(true);
  const [skillYears, setSkillYears] = useState<Record<string, string>>({});

  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveOk, setSaveOk] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!candidateId.trim()) return;
    setLoading(true);
    setLoadError(null);
    setSaveOk(null);
    setSaveError(null);
    setProfile(null);
    try {
      const profileRes: ApiResult = await callJson(
        `/api/v1/resumes/${candidateId.trim()}`,
        "GET"
      );
      if (!profileRes.ok) {
        setLoadError(`Candidate fetch failed: HTTP ${profileRes.status}`);
        setLoading(false);
        return;
      }
      const p = profileRes.body as CandidateProfile;
      setProfile(p);

      const prefRes: ApiResult = await callJson(
        `/api/v1/candidates/${candidateId.trim()}/preferences`,
        "GET"
      );
      const loaded: Preferences =
        prefRes.ok && (prefRes.body as { preferences?: Preferences })?.preferences
          ? (prefRes.body as { preferences: Preferences }).preferences
          : EMPTY;
      setPrefs(loaded);
      setNoticeDays(loaded.available_notice_days?.toString() ?? "");
      setSalaryMin(loaded.expected_salary?.min?.toString() ?? "");
      setSalaryMax(loaded.expected_salary?.max?.toString() ?? "");
      setCurrency(loaded.expected_salary?.currency ?? "INR");
      setLocationsCsv((loaded.preferred_locations ?? []).join(", "));
      setOpenToRemote(loaded.open_to_remote ?? true);

      const sy: Record<string, string> = {};
      for (const s of p.skills ?? []) {
        sy[s] = (loaded.skill_years[s] ?? "").toString();
      }
      setSkillYears(sy);
    } catch (err) {
      setLoadError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!profile) return;
    setSaving(true);
    setSaveError(null);
    setSaveOk(null);

    const body: Preferences = {
      available_notice_days: noticeDays ? parseInt(noticeDays, 10) : null,
      expected_salary:
        salaryMin && salaryMax
          ? {
              min: parseFloat(salaryMin),
              max: parseFloat(salaryMax),
              currency,
            }
          : null,
      preferred_locations: locationsCsv
        .split(",")
        .map((s) => s.trim().toLowerCase())
        .filter(Boolean),
      skill_years: Object.fromEntries(
        Object.entries(skillYears)
          .filter(([, v]) => v && parseFloat(v) >= 0)
          .map(([k, v]) => [k.toLowerCase(), parseFloat(v)])
      ),
      open_to_remote: openToRemote,
    };

    try {
      const res = await callJson(
        `/api/v1/candidates/${profile.id}/preferences`,
        "PUT",
        body
      );
      if (!res.ok) {
        setSaveError(`HTTP ${res.status}: ${JSON.stringify(res.body)}`);
        return;
      }
      setSaveOk("Saved.");
      setPrefs(body);
    } catch (err) {
      setSaveError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <main>
      <div className="crumbs"><Link href="/">← Home</Link></div>
      <h1>Candidate Preferences</h1>
      <p className="lede">
        Capture the bits that the resume doesn&apos;t carry: notice period, salary
        expectations, preferred locations, and per-skill years. Used by the Match
        Engine for the three new sub-scores (location, notice, salary) and to
        evaluate per-skill minimum-years requirements on JDs.
      </p>

      <form className="tester" onSubmit={load}>
        <div>
          <label>Candidate id (UUID)</label>
          <input
            type="text"
            value={candidateId}
            onChange={(e) => setCandidateId(e.target.value)}
            placeholder="9b8d6f0a-..."
          />
        </div>
        <button type="submit" disabled={loading}>{loading ? "Loading…" : "Load candidate"}</button>
        {loadError && (
          <div className="response err"><pre>{loadError}</pre></div>
        )}
      </form>

      {profile && (
        <form onSubmit={save} style={{ marginTop: 24 }}>
          <section style={cardStyle}>
            <h2 style={{ marginTop: 0 }}>{profile.full_name}</h2>
            <div style={{ color: "#9ca3af", fontSize: 13 }}>
              {[profile.email, profile.location, profile.headline].filter(Boolean).join(" · ")}
            </div>
          </section>

          <section style={cardStyle}>
            <h2 style={{ marginTop: 0 }}>Availability</h2>
            <Row label="Available notice (days)">
              <input
                type="number"
                min={0}
                max={365}
                value={noticeDays}
                onChange={(e) => setNoticeDays(e.target.value)}
                placeholder="e.g. 30"
                style={inputStyle}
              />
            </Row>
            <Row label="Open to remote">
              <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}>
                <input type="checkbox" checked={openToRemote} onChange={(e) => setOpenToRemote(e.target.checked)} />
                {openToRemote ? "Yes" : "No"}
              </label>
            </Row>
            <Row label="Preferred locations (comma-separated)">
              <input
                type="text"
                value={locationsCsv}
                onChange={(e) => setLocationsCsv(e.target.value)}
                placeholder="bengaluru, remote, hyderabad"
                style={inputStyle}
              />
            </Row>
          </section>

          <section style={cardStyle}>
            <h2 style={{ marginTop: 0 }}>Expected salary</h2>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              <Row label="Min">
                <input
                  type="number"
                  min={0}
                  value={salaryMin}
                  onChange={(e) => setSalaryMin(e.target.value)}
                  placeholder="1500000"
                  style={{ ...inputStyle, width: 160 }}
                />
              </Row>
              <Row label="Max">
                <input
                  type="number"
                  min={0}
                  value={salaryMax}
                  onChange={(e) => setSalaryMax(e.target.value)}
                  placeholder="2500000"
                  style={{ ...inputStyle, width: 160 }}
                />
              </Row>
              <Row label="Currency">
                <select value={currency} onChange={(e) => setCurrency(e.target.value)} style={{ ...inputStyle, width: 100 }}>
                  {["INR", "USD", "EUR", "GBP", "SGD", "AED"].map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </Row>
            </div>
            <p style={{ color: "#6b7280", fontSize: 11, margin: "8px 0 0" }}>
              Leave blank to opt out — the salary sub-score falls back to neutral (50).
            </p>
          </section>

          <section style={cardStyle}>
            <h2 style={{ marginTop: 0 }}>Skill years</h2>
            <p style={{ color: "#9ca3af", fontSize: 13, marginTop: 0 }}>
              Years of hands-on experience per skill. Blank entries default to
              the candidate&apos;s total experience (computed from work history).
            </p>
            {profile.skills.length === 0 ? (
              <p style={{ color: "#fde68a", fontSize: 13 }}>
                No skills on this candidate yet — re-parse the resume.
              </p>
            ) : (
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr style={{ color: "#9ca3af", textAlign: "left" }}>
                    <th style={th}>Skill</th>
                    <th style={th}>Years</th>
                  </tr>
                </thead>
                <tbody>
                  {profile.skills.map((s) => (
                    <tr key={s} style={{ borderBottom: "1px solid #1a1d24" }}>
                      <td style={td}>{s}</td>
                      <td style={td}>
                        <input
                          type="number"
                          min={0}
                          max={50}
                          step={0.5}
                          value={skillYears[s] ?? ""}
                          onChange={(e) =>
                            setSkillYears((prev) => ({ ...prev, [s]: e.target.value }))
                          }
                          style={{ ...inputStyle, width: 100 }}
                          placeholder="—"
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <div style={{ marginTop: 16 }}>
            <button type="submit" disabled={saving} style={{
              background: "#2563eb", color: "white", border: "none",
              padding: "10px 20px", borderRadius: 6, fontSize: 13, cursor: "pointer",
            }}>
              {saving ? "Saving…" : "Save preferences"}
            </button>
            {saveOk && <span style={{ marginLeft: 12, color: "#86efac", fontSize: 13 }}>✓ {saveOk}</span>}
            {saveError && (
              <div className="response err" style={{ marginTop: 12 }}>
                <pre>{saveError}</pre>
              </div>
            )}
          </div>
        </form>
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
const inputStyle: React.CSSProperties = {
  background: "#0b0d12",
  border: "1px solid #2a2f3a",
  color: "#e6e6e6",
  fontFamily: "ui-monospace, monospace",
  fontSize: 13,
  padding: "8px 10px",
  borderRadius: 4,
};
const th: React.CSSProperties = { padding: "6px 6px", borderBottom: "1px solid #2a2f3a" };
const td: React.CSSProperties = { padding: "6px 6px" };

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <label style={{ display: "block", color: "#9ca3af", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 4 }}>
        {label}
      </label>
      {children}
    </div>
  );
}

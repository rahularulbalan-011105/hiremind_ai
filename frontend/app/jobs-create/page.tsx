import Link from "next/link";
import JsonTester from "@/components/JsonTester";

const sample = {
  title: "Senior Backend Engineer (Python)",
  description:
    "Own our async data pipeline. FastAPI + Celery + Postgres. Embedding pipelines and vector search a plus. You'll work closely with the ML team on the candidate ranker.",
  company: "Acme",
  location: "Bengaluru",
  employment_type: "full_time",
  required_skills: [
    { skill: "python", min_years: 5 },
    { skill: "fastapi", min_years: 3 },
    { skill: "postgresql", min_years: 4 },
    { skill: "celery", min_years: 2 },
    { skill: "aws", min_years: 2 },
  ],
  required_years_experience: 5,
  notice_period_days_max: 60,
  salary: { min: 2000000, max: 3500000, currency: "INR" },
};

export default function Page() {
  return (
    <main>
      <div className="crumbs"><Link href="/">← Home</Link></div>
      <h1>Create Job</h1>
      <p className="lede">
        Creates a job posting AND generates the JD embedding synchronously.
        Required for the Match Engine — without a JD embedding,{" "}
        <code>/match/score</code> returns 404.
      </p>
      <p className="lede">
        Fields:
        <br />• <strong>required_skills</strong> — array of <code>{`{skill, min_years}`}</code>. A candidate matches a skill only if they list it AND have ≥ <code>min_years</code> on it.
        <br />• <strong>notice_period_days_max</strong> — the longest notice you&apos;ll accept (used by the new <em>notice</em> match dimension).
        <br />• <strong>salary</strong> — the budget you&apos;re hiring for (used by the new <em>salary</em> match dimension). Leave blank to skip.
      </p>
      <JsonTester method="POST" path="/api/v1/jobs" defaultBody={sample} />
    </main>
  );
}

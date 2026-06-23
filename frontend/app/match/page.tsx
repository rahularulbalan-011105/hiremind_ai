import Link from "next/link";
import JsonTester from "@/components/JsonTester";

const sample = {
  candidate_id: "11111111-1111-1111-1111-111111111111",
  job_id: "22222222-2222-2222-2222-222222222222",
  force_recompute: false,
  weights: {
    semantic: 0.25,
    skill_overlap: 0.25,
    experience: 0.15,
    location: 0.10,
    notice_period: 0.10,
    salary: 0.15,
  },
};

export default function Page() {
  return (
    <main>
      <div className="crumbs"><Link href="/">← Home</Link></div>
      <h1>AI Match Engine</h1>
      <p className="lede">
        Scores a candidate against a job on six dimensions: semantic similarity
        (resume vs JD embedding), skill overlap (vs JD&apos;s required skills with
        per-skill min years), experience relevance, location, notice period, and
        salary. Returns a composite 0–100 plus LLM-generated reasoning bullets.
      </p>
      <p className="lede">
        Prereq: both the candidate and the job must have embeddings stored, and
        notice/salary/location matching only contributes meaningfully when
        candidate preferences are set on{" "}
        <Link href="/candidate-preferences">Candidate Preferences</Link>.
      </p>
      <JsonTester method="POST" path="/api/v1/match/score" defaultBody={sample} />
    </main>
  );
}

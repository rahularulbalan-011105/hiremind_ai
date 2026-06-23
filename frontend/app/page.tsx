import Link from "next/link";

type Entry = {
  href: string;
  title: string;
  endpoint: string;
};

const entries: Entry[] = [
  { href: "/resume-parser",      title: "1. Resume Parser",            endpoint: "POST /api/v1/resumes/parse" },
  { href: "/resume-get",         title: "1b. Get Candidate",           endpoint: "GET  /api/v1/resumes/{id}" },
  { href: "/candidate-preferences", title: "1c. Candidate Preferences", endpoint: "PUT  /api/v1/candidates/{id}/preferences" },
  { href: "/embeddings",         title: "2. Embeddings",               endpoint: "POST /api/v1/embeddings/generate" },
  { href: "/vector-search",      title: "2b. Vector Search",           endpoint: "POST /api/v1/vector-search/candidates" },
  { href: "/jobs-create",        title: "3a. Create Job",              endpoint: "POST /api/v1/jobs" },
  { href: "/match",              title: "3. AI Match Engine",          endpoint: "POST /api/v1/match/score" },
  { href: "/match-by-job",       title: "3b. Match by Job (recruiter)", endpoint: "POST /api/v1/match/by-job" },
  { href: "/rank",               title: "4. Candidate Ranker",         endpoint: "POST /api/v1/rank/candidates" },
  { href: "/rank-compare",       title: "4b. Compare Candidates",      endpoint: "POST /api/v1/rank/compare" },
  { href: "/fake-profile",       title: "5. Fake Profile Detector",    endpoint: "POST /api/v1/fake-profile/score" },
  { href: "/duplicate-check",    title: "6. Duplicate Detector",       endpoint: "POST /api/v1/jobs/duplicate-check" },
  { href: "/ghost-score",        title: "7. Ghost Job Detector",       endpoint: "POST /api/v1/jobs/ghost-score" },
  { href: "/hiring-probability", title: "8. Hiring Probability",       endpoint: "POST /api/v1/hiring-probability/predict" },
];

export default function Home() {
  return (
    <main>
      <h1>HRMS AI — Test Harness</h1>
      <p className="lede">
        Dev-only UI for exercising the 8 AI modules. Talks directly to the FastAPI service at{" "}
        <code>NEXT_PUBLIC_API_BASE_URL</code>.
      </p>

      <h2>Modules</h2>
      <nav className="module-list">
        {entries.map((e) => (
          <Link key={e.href} href={e.href}>
            {e.title}
            <span className="endpoint">{e.endpoint}</span>
          </Link>
        ))}
      </nav>
    </main>
  );
}

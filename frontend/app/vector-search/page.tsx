import Link from "next/link";
import JsonTester from "@/components/JsonTester";

const sample = {
  query_text: "FastAPI engineer with pgvector and Celery experience",
  top_k: 10,
  filters: {
    location: null,
    min_experience_years: 3,
  },
};

export default function Page() {
  return (
    <main>
      <div className="crumbs"><Link href="/">← Home</Link></div>
      <h1>Vector Search — Candidates</h1>
      <p className="lede">Cosine similarity top-N search over <code>resume_embeddings</code>.</p>
      <JsonTester method="POST" path="/api/v1/vector-search/candidates" defaultBody={sample} />
    </main>
  );
}

import Link from "next/link";
import JsonTester from "@/components/JsonTester";

const sample = {
  kind: "resume",
  text: "Senior Python engineer with 7 years building FastAPI services. Strong in PostgreSQL, Celery, and AWS. Led migration of a monolith to event-driven microservices.",
};

export default function Page() {
  return (
    <main>
      <div className="crumbs"><Link href="/">← Home</Link></div>
      <h1>Embeddings — Generate</h1>
      <p className="lede">Generates a sentence-transformers embedding and stores it in pgvector.</p>
      <JsonTester method="POST" path="/api/v1/embeddings/generate" defaultBody={sample} />
    </main>
  );
}

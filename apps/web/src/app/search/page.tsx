import { Suspense } from "react";
import { SemanticSearch } from "@/features/search";

export default function SearchPage() {
  return (
    <Suspense
      fallback={
        <div role="status" className="text-sm text-muted">
          Preparing evidence search…
        </div>
      }
    >
      <SemanticSearch />
    </Suspense>
  );
}

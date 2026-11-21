import { Suspense } from "react";
import { Dashboard } from "@/features/dashboard";

export default function DashboardPage() {
  return (
    <Suspense
      fallback={
        <div role="status" className="text-sm text-muted">
          Preparing decision queue…
        </div>
      }
    >
      <Dashboard />
    </Suspense>
  );
}

import { AppShell } from "@/components/app-shell";
import { OpportunityDetail } from "@/features/opportunity-detail";

export default async function OpportunityPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <AppShell>
      <OpportunityDetail id={id} />
    </AppShell>
  );
}

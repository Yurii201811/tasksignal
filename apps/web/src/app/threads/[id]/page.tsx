import { OpportunityThreadDetail } from "@/features/opportunity-thread-detail";

export default async function OpportunityThreadPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <OpportunityThreadDetail id={id} />;
}

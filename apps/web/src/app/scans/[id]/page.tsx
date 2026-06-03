import { AppShell } from "@/components/app-shell";
import { ScanDetail } from "@/features/scan-detail";

export default async function ScanDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return (
    <AppShell>
      <ScanDetail id={id} />
    </AppShell>
  );
}

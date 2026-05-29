import { AppShell } from "@/components/app-shell";
import { PromptView } from "@/features/prompt-view";

export default async function PromptPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <AppShell>
      <PromptView id={id} />
    </AppShell>
  );
}

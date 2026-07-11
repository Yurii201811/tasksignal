import { PromptView } from "@/features/prompt-view";

export default async function PromptPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <>
      <PromptView id={id} />
    </>
  );
}

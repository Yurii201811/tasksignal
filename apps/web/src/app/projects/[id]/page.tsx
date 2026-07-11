import { ProjectRunHistory } from "@/features/project-run-history";

export default async function ProjectRunHistoryPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ProjectRunHistory id={id} />;
}

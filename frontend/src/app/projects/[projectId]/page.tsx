import AppShell from "@/components/AppShell";

export default async function ProjectCanvasPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  return <AppShell mode="project" projectId={projectId} step="canvas" />;
}

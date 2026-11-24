import AppShell, { ProjectStep } from "@/components/AppShell";

const VALID_STEPS: ReadonlySet<string> = new Set([
  "canvas",
  "upload",
  "preclean",
  "ai",
  "qc",
  "export",
]);

export default async function ProjectStepPage({
  params,
}: {
  params: Promise<{ projectId: string; step: string }>;
}) {
  const { projectId, step } = await params;
  const resolvedStep: ProjectStep = VALID_STEPS.has(step)
    ? (step as ProjectStep)
    : "canvas";
  return <AppShell mode="project" projectId={projectId} step={resolvedStep} />;
}

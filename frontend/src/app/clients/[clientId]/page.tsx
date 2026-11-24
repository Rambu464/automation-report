import AppShell from "@/components/AppShell";

export default async function ClientDetailConfigPage({
  params,
}: {
  params: Promise<{ clientId: string }>;
}) {
  const { clientId } = await params;
  return <AppShell mode="client_detail" clientId={clientId} />;
}

import { VerificationDossier } from "@/features/verification/components/verification-dossier";

export default async function Page({ params }: Readonly<{ params: Promise<{ id: string }> }>) {
  const { id } = await params;
  return <VerificationDossier key={id} analysisId={id} />;
}

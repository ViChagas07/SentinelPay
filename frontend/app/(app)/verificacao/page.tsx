import { VerificationPage } from "@/features/verification/components/verification-page";

type PageProps = {
  searchParams: Promise<{ tipo?: string | string[] }>;
};

export default async function Page({ searchParams }: PageProps) {
  const raw = (await searchParams).tipo;
  const value = Array.isArray(raw) ? raw[0] : raw;
  const initialKind = value === "boleto" || value === "payslip" ? value : undefined;

  return <VerificationPage initialKind={initialKind} />;
}

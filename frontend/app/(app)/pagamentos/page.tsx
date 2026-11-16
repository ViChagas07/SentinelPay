import { PaymentsPage } from "@/features/payments/components/payments-page";

type PageProps = {
  searchParams: Promise<{ vencimento?: string | string[] }>;
};

export default async function Page({ searchParams }: PageProps) {
  const raw = (await searchParams).vencimento;
  const value = Array.isArray(raw) ? raw[0] : raw;
  const focusPayableId = value?.trim() || undefined;

  return <PaymentsPage key={focusPayableId ?? "none"} focusPayableId={focusPayableId} />;
}

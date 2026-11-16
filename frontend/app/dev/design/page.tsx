import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { DesignShowcase } from "./design-showcase";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Design system",
  robots: {
    index: false,
    follow: false,
  },
};

export default function DesignPage() {
  if (process.env.NODE_ENV !== "development") {
    notFound();
  }

  return <DesignShowcase />;
}

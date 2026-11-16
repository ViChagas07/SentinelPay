import { Suspense } from "react";

import {
  AnalysisLibraryFallback,
  AnalysisLibraryPage,
} from "@/features/analyses/components/analysis-library-page";

export default function Page() {
  return (
    <Suspense fallback={<AnalysisLibraryFallback />}>
      <AnalysisLibraryPage kind="payslip" />
    </Suspense>
  );
}

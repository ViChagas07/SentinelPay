import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export type PageTransitionProps = {
  children: ReactNode;
  className?: string;
};

export function PageTransition({ children, className }: PageTransitionProps) {
  return <div className={cn("page-transition", className)}>{children}</div>;
}

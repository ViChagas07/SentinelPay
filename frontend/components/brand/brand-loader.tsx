import { cn } from "@/lib/utils";

import { Logo } from "./logo";

export type BrandLoaderProps = {
  className?: string;
  title?: string;
};

export function BrandLoader({ className, title }: BrandLoaderProps) {
  return (
    <span
      className={cn("inline-flex motion-safe:animate-pulse motion-reduce:animate-none", className)}
    >
      <Logo className="size-full" title={title} sizes="40px" />
    </span>
  );
}

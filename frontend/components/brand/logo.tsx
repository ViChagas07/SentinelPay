import type * as React from "react";

import { cn } from "@/lib/utils";

export type LogoProps = React.ComponentProps<"svg"> & {
  title?: string;
};

export function Logo({ className, title, ...props }: LogoProps) {
  return (
    <svg
      viewBox="0 0 40 40"
      fill="none"
      className={cn("size-8", className)}
      role={title ? "img" : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
      {...props}
    >
      <path d="M20 2.5 37.5 20 20 37.5 2.5 20Z" stroke="currentColor" strokeWidth="1.25" />
      <path d="M8.5 20h23M13 16v8M20 13.5v13M27 16v8" stroke="currentColor" strokeWidth="1" />
    </svg>
  );
}

export type WordmarkProps = {
  name: string;
  className?: string;
};

export function Wordmark({ name, className }: WordmarkProps) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <Logo className="size-6 text-primary" />
      <span className="font-serif text-xl tracking-tight">{name}</span>
    </span>
  );
}

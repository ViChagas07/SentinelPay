import { cn } from "@/lib/utils";

export type EyebrowProps = {
  number: string;
  label: string;
  as?: "p" | "h2" | "h3";
  className?: string;
};

export function Eyebrow({ number, label, as: Component = "p", className }: EyebrowProps) {
  return (
    <Component
      className={cn(
        "flex flex-wrap items-baseline gap-x-2 gap-y-1 font-mono text-[0.65rem] uppercase tracking-[0.22em] text-muted-foreground",
        className,
      )}
    >
      <span className="tabular-nums">{number}</span>
      <span aria-hidden="true">/</span>
      <span className="min-w-0 break-words">{label}</span>
    </Component>
  );
}

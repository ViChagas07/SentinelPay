import { Eyebrow } from "@/components/ui/eyebrow";
import { cn } from "@/lib/utils";

import styles from "../landing.module.css";

export type SectionHeadingProps = {
  id: string;
  number: string;
  label: string;
  title: string;
  accent: string;
  description: string;
  tone?: "default" | "dark";
  className?: string;
};

export function SectionHeading({
  id,
  number,
  label,
  title,
  accent,
  description,
  tone = "default",
  className,
}: SectionHeadingProps) {
  const isDark = tone === "dark";

  return (
    <div className={cn("max-w-3xl", className)}>
      <Eyebrow number={number} label={label} className={isDark ? "text-on-petrol/80" : undefined} />
      <h2
        id={id}
        className={cn(
          "mt-4 font-serif text-4xl leading-[1.02] tracking-tight sm:text-5xl",
          isDark && "text-on-petrol",
        )}
      >
        {title} <em className={isDark ? styles.accentOnDark : styles.accent}>{accent}</em>
      </h2>
      <p
        className={cn(
          "mt-4 text-base leading-relaxed",
          isDark ? "text-on-petrol/80" : "text-muted-foreground",
        )}
      >
        {description}
      </p>
    </div>
  );
}

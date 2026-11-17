import { Logo } from "@/components/brand/logo";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type EmptyStateAction = {
  label: string;
  href?: string;
  onClick?: () => void;
};

export type EmptyStateProps = {
  title: string;
  description?: string;
  action?: EmptyStateAction;
  className?: string;
};

export function EmptyState({ title, description, action, className }: EmptyStateProps) {
  return (
    <section
      className={cn("flex flex-col items-start gap-3 border-t border-border pt-6", className)}
    >
      <Logo className="size-6 opacity-70" />
      <h2 className="max-w-xl font-serif text-3xl leading-tight tracking-tight sm:text-4xl">
        {title}
      </h2>
      {description ? (
        <p className="max-w-xl text-sm leading-relaxed text-muted-foreground">{description}</p>
      ) : null}
      {action ? (
        action.href ? (
          <Button asChild>
            <a href={action.href}>{action.label}</a>
          </Button>
        ) : (
          <Button onClick={action.onClick}>{action.label}</Button>
        )
      ) : null}
    </section>
  );
}

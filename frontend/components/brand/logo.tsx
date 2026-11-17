import Image from "next/image";

import { cn } from "@/lib/utils";

const LOGO_SOURCES = {
  compact: "/brand/logo-compact-512.png",
  compactLight: "/brand/logo-compact-light-512.png",
  brand: "/brand/logo-symbol-512.png",
  light: "/brand/logo-symbol-light-512.png",
  white: "/brand/logo-symbol-on-white-512.png",
} as const;

export type LogoVariant = keyof typeof LOGO_SOURCES;

export type LogoProps = {
  className?: string;
  title?: string;
  variant?: LogoVariant;
  priority?: boolean;
  sizes?: string;
};

function LogoImage({
  className,
  title,
  src,
  priority,
  sizes,
}: {
  className?: string;
  title?: string;
  src: string;
  priority: boolean;
  sizes: string;
}) {
  return (
    <Image
      src={src}
      alt={title ?? ""}
      width={512}
      height={512}
      priority={priority}
      sizes={sizes}
      className={cn("h-full w-auto shrink-0 object-contain", className)}
    />
  );
}

export function Logo({
  className,
  title,
  variant = "compact",
  priority = false,
  sizes = "32px",
}: LogoProps) {
  if (variant === "compact") {
    return (
      <>
        <span className={cn("brand-logo-on-light shrink-0", className)}>
          <LogoImage src={LOGO_SOURCES.compact} title={title} priority={priority} sizes={sizes} />
        </span>
        <span className={cn("brand-logo-on-dark shrink-0", className)}>
          <LogoImage
            src={LOGO_SOURCES.compactLight}
            title={title}
            priority={priority}
            sizes={sizes}
          />
        </span>
      </>
    );
  }

  return (
    <Image
      src={LOGO_SOURCES[variant]}
      alt={title ?? ""}
      width={512}
      height={512}
      priority={priority}
      sizes={sizes}
      className={cn("shrink-0 object-contain", className)}
    />
  );
}

export type WordmarkProps = {
  name: string;
  className?: string;
  variant?: Extract<LogoVariant, "compact" | "compactLight">;
  priority?: boolean;
};

export function Wordmark({
  name,
  className,
  variant = "compact",
  priority = false,
}: WordmarkProps) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <Logo
        className="h-7 w-auto"
        variant={variant}
        title={name}
        priority={priority}
        sizes="28px"
      />
      <span aria-hidden="true" className="font-serif text-xl tracking-tight">
        {name}
      </span>
    </span>
  );
}

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

export type WordmarkSize = "default" | "large";

const WORDMARK_SIZES: Record<
  WordmarkSize,
  { container: string; logo: string; logoSize: string; text: string }
> = {
  default: {
    container: "gap-2.5",
    logo: "h-7 w-auto",
    logoSize: "28px",
    text: "text-xl",
  },
  large: {
    container: "gap-3.5",
    logo: "h-11 w-auto",
    logoSize: "44px",
    text: "text-[2rem] leading-none",
  },
};

export type WordmarkProps = {
  name: string;
  className?: string;
  variant?: Extract<LogoVariant, "compact" | "compactLight">;
  priority?: boolean;
  size?: WordmarkSize;
};

export function Wordmark({
  name,
  className,
  variant = "compact",
  priority = false,
  size = "default",
}: WordmarkProps) {
  const sizing = WORDMARK_SIZES[size];

  return (
    <span className={cn("inline-flex items-center", sizing.container, className)}>
      <Logo
        className={sizing.logo}
        variant={variant}
        title={name}
        priority={priority}
        sizes={sizing.logoSize}
      />
      <span aria-hidden="true" className={cn("font-serif tracking-tight", sizing.text)}>
        {name}
      </span>
    </span>
  );
}

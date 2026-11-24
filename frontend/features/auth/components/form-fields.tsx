"use client";

import { Eye, EyeOff } from "lucide-react";
import { forwardRef, useId, useState, type InputHTMLAttributes } from "react";

import { useI18n } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

export type FormFieldProps = {
  label: string;
  error?: string;
  hint?: string;
  errorTone?: "default" | "danger";
  children: (ids: { inputId: string; describedBy: string | undefined }) => React.ReactNode;
};

export function FormField({
  label,
  error,
  hint,
  errorTone = "default",
  children,
}: FormFieldProps) {
  const inputId = useId();
  const errorId = `${inputId}-error`;
  const hintId = `${inputId}-hint`;
  const describedBy = error ? errorId : hint ? hintId : undefined;

  return (
    <div className="space-y-1.5">
      <label
        htmlFor={inputId}
        className="block font-mono text-[0.65rem] uppercase tracking-[0.18em] text-muted-foreground"
      >
        {label}
      </label>
      {children({ inputId, describedBy })}
      {error ? (
        <p
          id={errorId}
          role="alert"
          className={cn(
            "text-xs font-medium leading-relaxed",
            errorTone === "danger" ? "text-risk-high" : "text-foreground",
          )}
        >
          {error}
        </p>
      ) : hint ? (
        <p id={hintId} className="text-xs leading-relaxed text-muted-foreground">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

export type TextFieldProps = InputHTMLAttributes<HTMLInputElement> & {
  invalid?: boolean;
};

export const TextField = forwardRef<HTMLInputElement, TextFieldProps>(function TextField(
  { className, invalid, ...props },
  ref,
) {
  return (
    <input
      ref={ref}
      aria-invalid={invalid || undefined}
      className={cn(
        "h-11 w-full rounded-[6px] border border-border bg-surface px-3 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground/70",
        "focus-visible:border-petrol-primary focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        "disabled:cursor-not-allowed disabled:opacity-60",
        invalid && "border-foreground/50",
        className,
      )}
      {...props}
    />
  );
});

export type PasswordFieldProps = Omit<TextFieldProps, "type"> & {
  danger?: boolean;
};

export const PasswordField = forwardRef<HTMLInputElement, PasswordFieldProps>(
  function PasswordField({ className, invalid, danger, ...props }, ref) {
    const { t } = useI18n();
    const [visible, setVisible] = useState(false);

    return (
      <div className="relative">
        <input
          ref={ref}
          type={visible ? "text" : "password"}
          aria-invalid={invalid || undefined}
          className={cn(
            "h-11 w-full rounded-[6px] border border-border bg-surface pl-3 pr-11 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground/70",
            "focus-visible:border-petrol-primary focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
            "disabled:cursor-not-allowed disabled:opacity-60",
            invalid && "border-foreground/50",
            danger && "border-risk-high focus-visible:border-risk-high focus-visible:ring-risk-high",
            className,
          )}
          {...props}
        />
        <button
          type="button"
          onClick={() => setVisible((current) => !current)}
          aria-label={visible ? t("auth.password.hide") : t("auth.password.show")}
          aria-pressed={visible}
          disabled={props.disabled}
          className="absolute right-0 top-0 flex h-11 w-11 items-center justify-center rounded-[6px] text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:opacity-60"
        >
          {visible ? (
            <EyeOff className="size-4" aria-hidden="true" />
          ) : (
            <Eye className="size-4" aria-hidden="true" />
          )}
        </button>
      </div>
    );
  },
);

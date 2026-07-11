import { clsx } from "clsx";
import Link from "next/link";
import {
  ButtonHTMLAttributes,
  HTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
  forwardRef,
} from "react";

const focusRing =
  "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ts-focus-ring)]";
const motion =
  "motion-safe:transition-[color,background-color,border-color,opacity,transform] motion-safe:duration-200 motion-safe:ease-product";

type CardVariant =
  | "default"
  | "muted"
  | "success"
  | "warning"
  | "danger"
  | "compact";

const cardVariants: Record<CardVariant, string> = {
  default: "border-border bg-surface shadow-none",
  muted: "border-border bg-surface-muted shadow-none",
  success: "border-success-border bg-surface-success shadow-none",
  warning: "border-warning-border bg-surface-warning shadow-none",
  danger: "border-danger-border bg-surface-danger shadow-none",
  compact: "border-border bg-surface p-3 shadow-none",
};

export function Card({
  children,
  className,
  variant = "default",
  ...props
}: HTMLAttributes<HTMLElement> & {
  variant?: CardVariant;
}) {
  return (
    <section
      className={clsx(
        "min-w-0 rounded-product border",
        variant === "compact" ? "p-3" : "p-5",
        cardVariants[variant],
        className,
      )}
      {...props}
    >
      {children}
    </section>
  );
}

export function Badge({
  children,
  tone = "slate",
}: {
  children: ReactNode;
  tone?: "slate" | "green" | "amber" | "blue" | "red";
}) {
  const tones = {
    slate: "border-border bg-surface-muted text-muted",
    green: "border-success-border bg-surface-success text-success",
    amber: "border-warning-border bg-surface-warning text-warning",
    blue: "border-info-border bg-[var(--color-info-surface)] text-info",
    red: "border-danger-border bg-surface-danger text-danger",
  };
  return (
    <span
      className={clsx(
        "inline-flex max-w-full items-center rounded-md border px-2 py-1 text-xs font-semibold",
        tones[tone],
      )}
    >
      {children}
    </span>
  );
}

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md";

const buttonVariants: Record<ButtonVariant, string> = {
  primary:
    "border border-transparent bg-signal text-[var(--color-accent-ink)] hover:bg-[var(--ts-accent-hover)] motion-safe:active:translate-y-px",
  secondary:
    "border border-border-strong bg-surface text-ink hover:bg-surface-muted motion-safe:active:translate-y-px",
  ghost:
    "border border-transparent bg-transparent text-ink hover:bg-surface-muted motion-safe:active:translate-y-px",
  danger:
    "border border-transparent bg-danger text-[var(--color-accent-ink)] hover:opacity-90 motion-safe:active:translate-y-px",
};

const buttonSizes: Record<ButtonSize, string> = {
  sm: "min-h-11 gap-2 px-3 py-2 text-xs",
  md: "min-h-11 gap-2 px-4 py-2 text-sm",
};

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  function Button(
    {
      children,
      className,
      variant = "primary",
      size = "md",
      loading = false,
      disabled,
      type = "button",
      ...props
    },
    ref,
  ) {
    const isDisabled = disabled || loading;
    return (
      <button
        ref={ref}
        type={type}
        disabled={isDisabled}
        aria-busy={loading || undefined}
        data-loading={loading ? "true" : undefined}
        className={clsx(
          "inline-flex items-center justify-center whitespace-nowrap rounded-product font-semibold",
          focusRing,
          motion,
          buttonVariants[variant],
          buttonSizes[size],
          isDisabled && "cursor-not-allowed opacity-60",
          className,
        )}
        {...props}
      >
        {children}
      </button>
    );
  },
);

export function ButtonLink({
  href,
  children,
  className,
}: {
  href: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <Link
      href={href}
      className={clsx(
        "inline-flex min-h-11 items-center justify-center whitespace-nowrap rounded-product bg-signal px-4 py-2 text-sm font-semibold text-[var(--color-accent-ink)]",
        focusRing,
        motion,
        "hover:bg-[var(--ts-accent-hover)] motion-safe:active:translate-y-px",
        className,
      )}
    >
      {children}
    </Link>
  );
}

const fieldBase = clsx(
  "min-h-11 w-full min-w-0 rounded-product border border-border-strong bg-surface text-sm text-ink shadow-none",
  "outline outline-2 outline-offset-2 outline-transparent",
  focusRing,
  motion,
  "placeholder:text-muted",
  "hover:border-border-strong active:border-border-strong",
  "disabled:cursor-not-allowed disabled:bg-surface-muted disabled:text-muted disabled:opacity-80",
);

export type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  error?: boolean;
  success?: boolean;
};

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { className, error, success, ...props },
  ref,
) {
  return (
    <input
      ref={ref}
      aria-invalid={error || undefined}
      data-state={error ? "error" : success ? "success" : undefined}
      className={clsx(
        fieldBase,
        "px-3 py-2",
        error && "border-danger focus-visible:outline-danger",
        success && !error && "border-success focus-visible:outline-success",
        className,
      )}
      {...props}
    />
  );
});

export type SelectProps = SelectHTMLAttributes<HTMLSelectElement> & {
  error?: boolean;
  success?: boolean;
};

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  function Select({ className, error, success, children, ...props }, ref) {
    return (
      <select
        ref={ref}
        aria-invalid={error || undefined}
        data-state={error ? "error" : success ? "success" : undefined}
        className={clsx(
          fieldBase,
          "px-3 py-2",
          error && "border-danger focus-visible:outline-danger",
          success && !error && "border-success focus-visible:outline-success",
          className,
        )}
        {...props}
      >
        {children}
      </select>
    );
  },
);

export type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  error?: boolean;
  success?: boolean;
};

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  function Textarea({ className, error, success, ...props }, ref) {
    return (
      <textarea
        ref={ref}
        aria-invalid={error || undefined}
        data-state={error ? "error" : success ? "success" : undefined}
        className={clsx(
          fieldBase,
          "min-h-24 resize-y px-3 py-2",
          error && "border-danger focus-visible:outline-danger",
          success && !error && "border-success focus-visible:outline-success",
          className,
        )}
        {...props}
      />
    );
  },
);

export function PageHeader({
  title,
  description,
  actions,
  className,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <header
      className={clsx(
        "flex min-w-0 flex-col justify-between gap-4 sm:flex-row sm:items-end",
        className,
      )}
    >
      <div className="min-w-0">
        <h1 className="min-w-0 break-words text-2xl font-bold tracking-[-0.025em] text-ink [overflow-wrap:anywhere] sm:text-3xl">
          {title}
        </h1>
        {description ? (
          <p className="mt-2 max-w-3xl break-words text-base leading-7 text-muted">
            {description}
          </p>
        ) : null}
      </div>
      {actions ? (
        <div className="flex flex-wrap items-center gap-2 sm:shrink-0">
          {actions}
        </div>
      ) : null}
    </header>
  );
}

type StateTone = "info" | "success" | "warning" | "danger";

const stateTones: Record<StateTone, { surface: string; text: string }> = {
  info: {
    surface: "border-info-border bg-[var(--color-info-surface)]",
    text: "text-info",
  },
  success: {
    surface: "border-success-border bg-surface-success",
    text: "text-success",
  },
  warning: {
    surface: "border-warning-border bg-surface-warning",
    text: "text-warning",
  },
  danger: {
    surface: "border-danger-border bg-surface-danger",
    text: "text-danger",
  },
};

export function StateMessage({
  title,
  children,
  tone = "info",
  action,
  className,
}: {
  title: ReactNode;
  children?: ReactNode;
  tone?: StateTone;
  action?: ReactNode;
  className?: string;
}) {
  const styles = stateTones[tone];
  return (
    <div
      className={clsx(
        "min-w-0 rounded-product border px-4 py-3",
        styles.surface,
        className,
      )}
      role={tone === "danger" ? "alert" : "status"}
      aria-atomic="true"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 text-sm">
          <p className={clsx("font-semibold", styles.text)}>{title}</p>
          {children ? (
            <div className="mt-1 break-words text-muted">{children}</div>
          ) : null}
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
  className,
}: {
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <Card variant="muted" className={clsx("text-center", className)}>
      <p className="text-sm font-semibold text-ink">{title}</p>
      {description ? (
        <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted">
          {description}
        </p>
      ) : null}
      {action ? <div className="mt-4 flex justify-center">{action}</div> : null}
    </Card>
  );
}

export function TableShell({
  children,
  caption,
  label,
  className,
  tableClassName,
}: {
  children: ReactNode;
  caption?: ReactNode;
  label?: string;
  className?: string;
  tableClassName?: string;
}) {
  return (
    <div
      className={clsx(
        "min-w-0 overflow-x-auto rounded-product focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ts-focus-ring)]",
        className,
      )}
      role={label ? "region" : undefined}
      aria-label={label}
      tabIndex={label ? 0 : undefined}
    >
      <table
        className={clsx("w-full min-w-0 text-left text-sm", tableClassName)}
      >
        {caption ? <caption className="sr-only">{caption}</caption> : null}
        {children}
      </table>
    </div>
  );
}

export function MetricTile({
  label,
  value,
  hint,
  className,
}: {
  label: ReactNode;
  value: ReactNode;
  hint?: ReactNode;
  className?: string;
}) {
  return (
    <Card variant="default" className={className}>
      <p className="text-sm font-medium text-muted">{label}</p>
      <p className="mt-2 text-3xl font-semibold tabular-nums text-ink">
        {value}
      </p>
      {hint ? <p className="mt-1 text-xs text-muted">{hint}</p> : null}
    </Card>
  );
}

export function ScoreBar({ value, label }: { value: number; label: string }) {
  const width = `${Math.round(Math.min(1, Math.max(0, value)) * 100)}%`;
  const percent = Math.round(value * 100);
  return (
    <div
      className="h-2 w-full overflow-hidden rounded-full bg-surface-muted"
      role="meter"
      aria-label={label}
      aria-valuenow={percent}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuetext={`${percent} percent`}
    >
      <div className="h-2 rounded-full bg-signal" style={{ width }} />
    </div>
  );
}

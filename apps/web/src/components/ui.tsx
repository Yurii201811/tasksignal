import { clsx } from "clsx";
import Link from "next/link";
import {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  forwardRef,
} from "react";

const focusRing =
  "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ts-focus-ring)]";
const motion =
  "motion-safe:transition-[color,background-color,border-color,box-shadow,opacity] motion-safe:duration-200 motion-safe:ease-product";

type CardVariant = "default" | "muted" | "success" | "warning" | "danger" | "compact";

const cardVariants: Record<CardVariant, string> = {
  default: "border-border bg-surface shadow-soft",
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
}: {
  children: ReactNode;
  className?: string;
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
    slate: "bg-surface-muted text-muted",
    green: "bg-surface-success text-success",
    amber: "bg-surface-warning text-warning",
    blue: "bg-[color-mix(in_srgb,var(--ts-info)_8%,var(--ts-surface))] text-info",
    red: "bg-surface-danger text-danger",
  };
  return (
    <span
      className={clsx(
        "inline-flex max-w-full items-center rounded-md px-2 py-1 text-xs font-semibold",
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
    "border border-transparent bg-signal text-[color-mix(in_srgb,var(--ts-surface)_96%,transparent)] hover:bg-[var(--ts-accent-hover)] active:opacity-90",
  secondary:
    "border border-border bg-surface text-ink hover:bg-surface-muted active:bg-surface-muted",
  ghost:
    "border border-transparent bg-transparent text-ink hover:bg-surface-muted active:bg-surface-muted",
  danger:
    "border border-transparent bg-danger text-[color-mix(in_srgb,var(--ts-surface)_96%,transparent)] hover:opacity-90 active:opacity-85",
};

const buttonSizes: Record<ButtonSize, string> = {
  sm: "min-h-9 gap-1.5 px-3 py-1.5 text-xs",
  md: "min-h-11 gap-2 px-4 py-2 text-sm",
};

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
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
        "inline-flex items-center justify-center rounded-product font-semibold",
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
});

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
        "inline-flex min-h-11 items-center justify-center rounded-product bg-signal px-4 py-2 text-sm font-semibold text-[color-mix(in_srgb,var(--ts-surface)_96%,transparent)]",
        focusRing,
        motion,
        "hover:bg-[var(--ts-accent-hover)] active:opacity-90",
        className,
      )}
    >
      {children}
    </Link>
  );
}

const fieldBase = clsx(
  "w-full min-w-0 rounded-product border border-border bg-surface text-sm text-ink shadow-sm",
  focusRing,
  motion,
  "placeholder:text-muted",
  "hover:border-border-strong",
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
        error && "border-danger-border focus-visible:outline-danger",
        success && !error && "border-success-border focus-visible:outline-success",
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

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { className, error, success, children, ...props },
  ref,
) {
  return (
    <select
      ref={ref}
      aria-invalid={error || undefined}
      data-state={error ? "error" : success ? "success" : undefined}
      className={clsx(
        fieldBase,
        "px-3 py-2",
        error && "border-danger-border focus-visible:outline-danger",
        success && !error && "border-success-border focus-visible:outline-success",
        className,
      )}
      {...props}
    >
      {children}
    </select>
  );
});

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
        "flex flex-col justify-between gap-4 sm:flex-row sm:items-end",
        className,
      )}
    >
      <div className="min-w-0">
        <h1 className="text-3xl font-semibold tracking-tight text-ink">{title}</h1>
        {description ? (
          <p className="mt-2 max-w-3xl text-base leading-7 text-muted">{description}</p>
        ) : null}
      </div>
      {actions ? (
        <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>
      ) : null}
    </header>
  );
}

type StateTone = "info" | "success" | "warning" | "danger";

const stateTones: Record<StateTone, { card: CardVariant; text: string }> = {
  info: { card: "muted", text: "text-info" },
  success: { card: "success", text: "text-success" },
  warning: { card: "warning", text: "text-warning" },
  danger: { card: "danger", text: "text-danger" },
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
    <Card variant={styles.card} className={className}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 text-sm">
          <p className={clsx("font-semibold", styles.text)}>{title}</p>
          {children ? (
            <div className="mt-1 break-words text-muted">{children}</div>
          ) : null}
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
    </Card>
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
        <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted">{description}</p>
      ) : null}
      {action ? <div className="mt-4 flex justify-center">{action}</div> : null}
    </Card>
  );
}

export function TableShell({
  children,
  caption,
  className,
  tableClassName,
}: {
  children: ReactNode;
  caption?: ReactNode;
  className?: string;
  tableClassName?: string;
}) {
  return (
    <div className={clsx("min-w-0 overflow-x-auto", className)}>
      <table className={clsx("w-full min-w-0 text-left text-sm", tableClassName)}>
        {children}
      </table>
      {caption ? (
        <p className="mt-2 text-xs text-muted" role="note">
          {caption}
        </p>
      ) : null}
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
      <p className="mt-2 text-3xl font-semibold tabular-nums text-ink">{value}</p>
      {hint ? <p className="mt-1 text-xs text-muted">{hint}</p> : null}
    </Card>
  );
}

export function ScoreBar({ value }: { value: number }) {
  const width = `${Math.round(Math.min(1, Math.max(0, value)) * 100)}%`;
  return (
    <div
      className="h-2 w-full overflow-hidden rounded-full bg-surface-muted"
      role="meter"
      aria-valuenow={Math.round(value * 100)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className="h-2 rounded-full bg-signal motion-safe:transition-[width] motion-safe:duration-200 motion-safe:ease-product"
        style={{ width }}
      />
    </div>
  );
}

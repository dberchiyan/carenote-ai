import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "danger" | "ghost";
type Size = "md" | "sm";

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-brand text-brand-fg shadow-[inset_0_1px_0_rgb(255_255_255/0.18),0_1px_2px_rgb(15_23_42/0.12)] hover:bg-brand-strong disabled:bg-surface-3 disabled:text-ink-3 disabled:shadow-none dark:hover:bg-brand-strong",
  secondary:
    "bg-surface text-ink ring-1 ring-inset ring-line-strong shadow-[0_1px_2px_rgb(15_23_42/0.05)] hover:bg-surface-2 disabled:text-ink-3",
  danger:
    "bg-red-700 text-white shadow-[inset_0_1px_0_rgb(255_255_255/0.15)] hover:bg-red-800 disabled:bg-surface-3 disabled:text-ink-3",
  ghost: "text-ink-2 hover:bg-surface-3 hover:text-ink",
};

const SIZES: Record<Size, string> = {
  md: "min-h-11 px-4 text-sm",
  sm: "min-h-9 px-3 text-sm",
};

export function buttonClass(variant: Variant = "primary", size: Size = "md", className = "") {
  return `inline-flex items-center justify-center gap-2 rounded-xl py-2 font-semibold tracking-[-0.005em] transition-[background-color,box-shadow,color] duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-ring disabled:cursor-not-allowed ${VARIANTS[variant]} ${SIZES[size]} ${className}`;
}

export function Button({
  variant = "primary",
  size = "md",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size }) {
  return <button type="button" className={buttonClass(variant, size, className)} {...props} />;
}

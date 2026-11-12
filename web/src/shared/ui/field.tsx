"use client";

import { forwardRef, useId, type ReactNode } from "react";
import type { InputHTMLAttributes, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

import { ChevronDownIcon, SearchIcon, XIcon } from "@/shared/ui/icons";

/*
 * Form controls. One visual language for every input, select and textarea:
 * - 40px tall (36px `sm`), 10px radius, hover darkens the border, focus shows a 3px brand ring;
 * - `aria-invalid` turns the ring red; the message under the control is linked by id;
 * - selects are native (best keyboard and mobile behaviour) with our own chevron;
 * - adornments (a unit, an icon) sit inside the control, never as a loose span next to it.
 */

type Size = "md" | "sm";
const SIZE: Record<Size, string> = { md: "min-h-10 text-sm", sm: "min-h-9 text-sm" };

/** Label + control + hint/error. Wires ids and aria-describedby so nothing is announced twice. */
export function Field({
  label,
  hint,
  error,
  required,
  className = "",
  children,
}: {
  label: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  required?: boolean;
  className?: string;
  children: (props: { id: string; describedBy?: string; invalid: boolean }) => ReactNode;
}) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = [error ? errorId : null, hint ? hintId : null].filter(Boolean).join(" ");
  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      <label htmlFor={id} className="text-ink-2 text-xs font-medium">
        {label}
        {required && (
          <span aria-hidden="true" className="text-red-600">
            {" "}
            *
          </span>
        )}
      </label>
      {children({ id, describedBy: describedBy || undefined, invalid: !!error })}
      {error ? (
        <p id={errorId} role="alert" className="text-xs text-red-700 dark:text-red-300">
          {error}
        </p>
      ) : hint ? (
        <p id={hintId} className="text-ink-3 text-xs">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

type InputProps = Omit<InputHTMLAttributes<HTMLInputElement>, "size" | "prefix"> & {
  size?: Size;
  /** Inside the control, on the left (an icon) or right (a unit). Decorative. */
  prefix?: ReactNode;
  suffix?: ReactNode;
  invalid?: boolean;
};

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { size = "md", prefix, suffix, invalid, className = "", ...props },
  ref,
) {
  const control = (
    <input
      ref={ref}
      aria-invalid={invalid || undefined}
      className={`field ${SIZE[size]} ${prefix ? "pl-9" : ""} ${suffix ? "pr-14" : ""} ${className}`}
      {...props}
    />
  );
  if (!prefix && !suffix) return control;
  return (
    <span className="relative block">
      {prefix && (
        <span
          aria-hidden="true"
          className="text-ink-3 pointer-events-none absolute inset-y-0 left-3 flex items-center"
        >
          {prefix}
        </span>
      )}
      {control}
      {suffix && (
        <span
          aria-hidden="true"
          className="text-ink-3 pointer-events-none absolute inset-y-0 right-3 flex items-center text-xs font-medium"
        >
          {suffix}
        </span>
      )}
    </span>
  );
});

type SelectProps = Omit<SelectHTMLAttributes<HTMLSelectElement>, "size"> & {
  size?: Size;
  invalid?: boolean;
};

/** Native select with our chevron: keyboard, screen readers and mobile pickers all just work. */
export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { size = "md", invalid, className = "", children, ...props },
  ref,
) {
  return (
    <span className="relative block">
      <select
        ref={ref}
        aria-invalid={invalid || undefined}
        className={`field ${SIZE[size]} cursor-pointer appearance-none pr-9 ${className}`}
        {...props}
      >
        {children}
      </select>
      <ChevronDownIcon
        size={15}
        className="text-ink-3 pointer-events-none absolute top-1/2 right-3 -translate-y-1/2"
      />
    </span>
  );
});

type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement> & { invalid?: boolean };

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { invalid, className = "", ...props },
  ref,
) {
  return (
    <textarea
      ref={ref}
      aria-invalid={invalid || undefined}
      className={`field min-h-28 resize-y leading-relaxed ${className}`}
      {...props}
    />
  );
});

/** Search box: icon, Escape or the clear button empties it, optional keyboard hint. */
export const SearchInput = forwardRef<
  HTMLInputElement,
  Omit<InputHTMLAttributes<HTMLInputElement>, "size" | "type" | "value" | "onChange"> & {
    value: string;
    onChange: (value: string) => void;
    shortcut?: string;
    size?: Size;
  }
>(function SearchInput(
  { value, onChange, shortcut, size = "md", className = "", onKeyDown, ...props },
  ref,
) {
  return (
    <span className="relative block">
      <SearchIcon
        size={15}
        className="text-ink-3 pointer-events-none absolute top-1/2 left-3 -translate-y-1/2"
      />
      <input
        ref={ref}
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Escape") onChange("");
          onKeyDown?.(e);
        }}
        className={`field ${SIZE[size]} pl-9 ${value ? "pr-9" : shortcut ? "pr-10" : ""} ${className}`}
        {...props}
      />
      {value ? (
        <button
          type="button"
          aria-label="Clear search"
          onClick={() => onChange("")}
          className="text-ink-3 hover:bg-surface-3 hover:text-ink focus-visible:outline-brand-ring absolute top-1/2 right-1.5 flex size-7 -translate-y-1/2 items-center justify-center rounded-md focus-visible:outline-2"
        >
          <XIcon size={14} />
        </button>
      ) : (
        shortcut && (
          <kbd
            aria-hidden="true"
            className="text-ink-3 ring-line-strong/70 pointer-events-none absolute top-1/2 right-2.5 hidden -translate-y-1/2 rounded px-1.5 font-mono text-[10px] ring-1 sm:block"
          >
            {shortcut}
          </kbd>
        )
      )}
    </span>
  );
});

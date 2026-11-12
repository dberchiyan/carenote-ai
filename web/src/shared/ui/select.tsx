"use client";

import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";

import { CheckIcon, ChevronDownIcon, SearchIcon, XIcon } from "./icons";

/*
 * Select: the WAI-ARIA "select-only combobox" pattern, styled like every other control.
 *
 * - The trigger is a button with role="combobox"; labels (<label for>, a wrapping <label> or
 *   aria-label) name it exactly like a native control.
 * - Desktop: a popover under the trigger (flips above when there is no room), the selected
 *   option ticked, the active one highlighted, groups with headings, descriptions and hints.
 * - Phone: a bottom sheet with large rows, a title and a close button, within thumb reach.
 * - Keyboard: ↑ ↓ Home End PgUp PgDn, Enter/Space to choose, Esc to close, type to jump.
 *   Long lists (more than 8 options) get a search field that filters as you type.
 */

export type SelectOption<V extends string = string> = {
  value: V;
  label: string;
  /** A second line under the label. */
  description?: string;
  /** Right-aligned, muted: a unit, a count, a shortcut. */
  hint?: string;
  icon?: ReactNode;
  /** Options with the same group are listed under one heading, in order of first appearance. */
  group?: string;
  /** Extra words the search matches (an MRN, a room). */
  keywords?: string;
  disabled?: boolean;
};

type Size = "md" | "sm";
const TRIGGER: Record<Size, string> = {
  md: "min-h-11 text-base sm:min-h-10 sm:text-sm",
  sm: "min-h-10 text-base sm:min-h-9 sm:text-sm",
};
const SEARCH_THRESHOLD = 8;
const GAP = 6;
const EDGE = 8;

function subscribePhone(onChange: () => void) {
  const query = window.matchMedia?.("(max-width: 639px)");
  query?.addEventListener("change", onChange);
  return () => query?.removeEventListener("change", onChange);
}
const isPhone = () => window.matchMedia?.("(max-width: 639px)").matches ?? false;

function useIsPhone(): boolean {
  return useSyncExternalStore(subscribePhone, isPhone, () => false);
}

/** Case- and accent-insensitive "does the option match what was typed". */
export function matches(option: SelectOption, query: string): boolean {
  const needle = normalise(query.trim());
  if (!needle) return true;
  const hay = normalise(
    [option.label, option.description, option.hint, option.keywords, option.group]
      .filter(Boolean)
      .join(" "),
  );
  return needle.split(/\s+/).every((word) => hay.includes(word));
}
function normalise(text: string): string {
  return text
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();
}

export function Select<V extends string>({
  value,
  onChange,
  options,
  placeholder = "Select…",
  searchable,
  searchPlaceholder = "Search…",
  size = "md",
  invalid,
  disabled,
  id,
  title,
  mono = false,
  className = "",
  "aria-label": ariaLabel,
  "aria-describedby": ariaDescribedBy,
}: {
  value: V | null | undefined;
  onChange: (value: V) => void;
  options: readonly SelectOption<V>[];
  placeholder?: string;
  searchable?: boolean;
  searchPlaceholder?: string;
  size?: Size;
  invalid?: boolean;
  disabled?: boolean;
  id?: string;
  /** Heading of the phone sheet and name of the list; defaults to aria-label. */
  title?: string;
  /** Monospace labels, for codes and identifiers. */
  mono?: boolean;
  className?: string;
  "aria-label"?: string;
  "aria-describedby"?: string;
}) {
  const autoId = useId();
  const triggerId = id ?? `${autoId}-trigger`;
  const listId = `${autoId}-list`;
  const trigger = useRef<HTMLButtonElement>(null);
  const popover = useRef<HTMLDivElement>(null);
  const search = useRef<HTMLInputElement>(null);
  const typed = useRef({ text: "", at: 0 });
  const phone = useIsPhone();

  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(-1);
  const [place, setPlace] = useState<{
    top?: number;
    bottom?: number;
    left: number;
    width: number;
    maxHeight: number;
  } | null>(null);

  const withSearch = searchable ?? options.length > SEARCH_THRESHOLD;
  const visible = useMemo(
    () => (withSearch ? options.filter((o) => matches(o, query)) : options),
    [options, query, withSearch],
  );
  const selected = options.find((o) => o.value === value);
  const name = title ?? ariaLabel;

  const firstEnabled = useCallback(
    (from: number, step: 1 | -1) => {
      for (let i = from; i >= 0 && i < visible.length; i += step) {
        if (!visible[i]?.disabled) return i;
      }
      return -1;
    },
    [visible],
  );

  const show = useCallback(() => {
    if (disabled) return;
    setQuery("");
    const current = options.findIndex((o) => o.value === value);
    setActive(current >= 0 ? current : firstEnabled(0, 1));
    setOpen(true);
  }, [disabled, options, value, firstEnabled]);

  const hide = useCallback((refocus = true) => {
    setOpen(false);
    setQuery("");
    if (refocus) trigger.current?.focus();
  }, []);

  const choose = useCallback(
    (option: SelectOption<V> | undefined) => {
      if (!option || option.disabled) return;
      if (option.value !== value) onChange(option.value);
      hide();
    },
    [hide, onChange, value],
  );

  // Desktop placement: under the trigger, above it when the space below is too small.
  const position = useCallback(() => {
    const box = trigger.current?.getBoundingClientRect();
    if (!box) return;
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const width = Math.min(Math.max(box.width, 208), vw - EDGE * 2);
    const left = Math.min(Math.max(box.left, EDGE), vw - width - EDGE);
    const below = vh - box.bottom - GAP - EDGE;
    const above = box.top - GAP - EDGE;
    const flip = below < 220 && above > below;
    setPlace(
      flip
        ? { bottom: vh - box.top + GAP, left, width, maxHeight: Math.min(360, above) }
        : { top: box.bottom + GAP, left, width, maxHeight: Math.min(360, below) },
    );
  }, []);

  useLayoutEffect(() => {
    if (!open || phone) return;
    position();
    window.addEventListener("resize", position);
    window.addEventListener("scroll", position, true);
    return () => {
      window.removeEventListener("resize", position);
      window.removeEventListener("scroll", position, true);
    };
  }, [open, phone, position]);

  // Outside click closes; the sheet locks the page behind it.
  useEffect(() => {
    if (!open) return;
    const onPointer = (e: PointerEvent) => {
      const target = e.target as Node;
      if (!popover.current?.contains(target) && !trigger.current?.contains(target)) hide(false);
    };
    document.addEventListener("pointerdown", onPointer);
    const previous = document.body.style.overflow;
    if (phone) document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.body.style.overflow = previous;
    };
  }, [open, phone, hide]);

  useEffect(() => {
    // On a phone the keyboard would cover the sheet: the search is there, a tap away.
    if (open && withSearch && !phone) search.current?.focus({ preventScroll: true });
  }, [open, withSearch, phone]);

  useEffect(() => {
    if (!open || active < 0) return;
    document.getElementById(`${listId}-${active}`)?.scrollIntoView?.({ block: "nearest" });
  }, [open, active, listId]);

  /** Typing in the search filters the list and highlights the first match. */
  const filterBy = (text: string) => {
    setQuery(text);
    setActive(options.filter((o) => matches(o, text)).findIndex((o) => !o.disabled));
  };

  /** Move only when there is somewhere enabled to move to. */
  const keep = (current: number, next: number) => (next < 0 ? current : next);

  function jumpTo(char: string) {
    const now = Date.now();
    typed.current.text = now - typed.current.at > 700 ? char : typed.current.text + char;
    typed.current.at = now;
    const needle = normalise(typed.current.text);
    const start = typed.current.text.length > 1 ? Math.max(active, 0) : active + 1;
    const order = [...visible.keys()].map((i) => (start + i) % visible.length);
    const hit = order.find(
      (i) => !visible[i]?.disabled && normalise(visible[i]?.label ?? "").startsWith(needle),
    );
    if (hit !== undefined) setActive(hit);
  }

  function onKeyDown(e: KeyboardEvent) {
    if (!open) {
      if (["ArrowDown", "ArrowUp", "Enter", " "].includes(e.key)) {
        e.preventDefault();
        show();
      } else if (e.key.length === 1 && !e.metaKey && !e.ctrlKey && !e.altKey) {
        show();
        if (!withSearch) jumpTo(e.key.toLowerCase());
        else filterBy(e.key);
      }
      return;
    }
    const last = visible.length - 1;
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setActive((i) => keep(i, firstEnabled(Math.min(i + 1, last), 1)));
        return;
      case "ArrowUp":
        e.preventDefault();
        if (e.altKey) return choose(visible[active]);
        setActive((i) => keep(i, firstEnabled(Math.max(i - 1, 0), -1)));
        return;
      case "Home":
        if (withSearch) return;
        e.preventDefault();
        setActive(firstEnabled(0, 1));
        return;
      case "End":
        if (withSearch) return;
        e.preventDefault();
        setActive(firstEnabled(last, -1));
        return;
      case "PageDown":
        e.preventDefault();
        setActive((i) => keep(i, firstEnabled(Math.min(i + 8, last), 1)));
        return;
      case "PageUp":
        e.preventDefault();
        setActive((i) => keep(i, firstEnabled(Math.max(i - 8, 0), -1)));
        return;
      case "Enter":
        e.preventDefault();
        choose(visible[active]);
        return;
      case " ":
        if (withSearch) return; // a space is part of the search
        e.preventDefault();
        choose(visible[active]);
        return;
      case "Escape":
        e.preventDefault();
        hide();
        return;
      case "Tab":
        hide(false);
        return;
      default:
        if (!withSearch && e.key.length === 1 && !e.metaKey && !e.ctrlKey && !e.altKey) {
          jumpTo(e.key.toLowerCase());
        }
    }
  }

  const activeId = open && active >= 0 ? `${listId}-${active}` : undefined;

  // Groups in order of first appearance; options keep their index in `visible`.
  const groups = useMemo(() => {
    const out: { name?: string; items: { option: SelectOption<V>; index: number }[] }[] = [];
    visible.forEach((option, index) => {
      const last = out[out.length - 1];
      if (last && last.name === option.group) last.items.push({ option, index });
      else out.push({ name: option.group, items: [{ option, index }] });
    });
    return out;
  }, [visible]);

  const list = (
    <ul
      id={listId}
      role="listbox"
      aria-label={name}
      className={`flex flex-col overflow-y-auto overscroll-contain ${phone ? "px-2 pb-2" : "p-1"}`}
      style={
        phone ? undefined : { maxHeight: place ? place.maxHeight - (withSearch ? 52 : 0) : 320 }
      }
    >
      {visible.length === 0 && (
        <li role="presentation" className="text-ink-3 px-3 py-6 text-center text-sm">
          No matches for “{query}”
        </li>
      )}
      {groups.map((group, g) => (
        <li key={`${group.name ?? ""}-${g}`} role="presentation">
          {group.name && (
            <p id={`${listId}-g${g}`} className="eyebrow px-3 pt-2.5 pb-1" aria-hidden="true">
              {group.name}
            </p>
          )}
          <ul role="group" aria-labelledby={group.name ? `${listId}-g${g}` : undefined}>
            {group.items.map(({ option, index }) => {
              const isSelected = option.value === value;
              const isActive = index === active;
              return (
                <li
                  key={option.value}
                  id={`${listId}-${index}`}
                  role="option"
                  aria-selected={isSelected}
                  aria-disabled={option.disabled || undefined}
                  onPointerMove={() => !option.disabled && setActive(index)}
                  onClick={() => choose(option)}
                  className={`flex cursor-pointer items-center gap-3 rounded-lg px-3 select-none ${
                    phone ? "min-h-12 py-2.5 text-base" : "min-h-9 py-2 text-sm"
                  } ${
                    option.disabled
                      ? "text-ink-3 cursor-not-allowed opacity-60"
                      : isActive
                        ? "bg-surface-3 text-ink"
                        : "text-ink-2"
                  }`}
                >
                  {option.icon && (
                    <span aria-hidden="true" className="text-ink-3 flex shrink-0">
                      {option.icon}
                    </span>
                  )}
                  <span className="min-w-0 flex-1">
                    <span
                      className={`block truncate ${isSelected ? "text-ink font-semibold" : ""} ${
                        mono && option.value ? "font-mono text-[0.92em]" : ""
                      }`}
                    >
                      {option.label}
                    </span>
                    {option.description && (
                      <span className="text-ink-3 block truncate text-xs">
                        {option.description}
                      </span>
                    )}
                  </span>
                  {option.hint && (
                    <span className="text-ink-3 shrink-0 text-xs tabular-nums">{option.hint}</span>
                  )}
                  <CheckIcon
                    size={16}
                    aria-hidden="true"
                    className={`text-brand-text shrink-0 ${isSelected ? "" : "invisible"}`}
                  />
                </li>
              );
            })}
          </ul>
        </li>
      ))}
    </ul>
  );

  const searchField = withSearch && (
    <div className={phone ? "px-4 pb-2" : "border-line border-b p-1.5"}>
      <span className="relative block">
        <SearchIcon
          size={15}
          className="text-ink-3 pointer-events-none absolute top-1/2 left-3 -translate-y-1/2"
        />
        <input
          ref={search}
          type="text"
          role="searchbox"
          aria-label={`Search ${name ?? "options"}`}
          aria-controls={listId}
          aria-activedescendant={activeId}
          autoComplete="off"
          spellCheck={false}
          value={query}
          placeholder={searchPlaceholder}
          onChange={(e) => filterBy(e.target.value)}
          onKeyDown={onKeyDown}
          className={`bg-surface-2 text-ink placeholder:text-ink-3 focus-visible:outline-brand-ring w-full rounded-lg pr-3 pl-9 focus-visible:outline-2 ${
            phone ? "h-11 text-base" : "h-9 text-sm"
          }`}
        />
      </span>
    </div>
  );

  return (
    <>
      <button
        ref={trigger}
        id={triggerId}
        type="button"
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        aria-activedescendant={!withSearch ? activeId : undefined}
        aria-label={ariaLabel}
        aria-describedby={ariaDescribedBy}
        aria-invalid={invalid || undefined}
        disabled={disabled}
        onClick={() => (open ? hide() : show())}
        onKeyDown={onKeyDown}
        className={`field ${TRIGGER[size]} flex w-full cursor-pointer items-center gap-2 text-left ${
          open
            ? "border-[var(--brand-ring)] shadow-[0_0_0_3px_color-mix(in_oklab,var(--brand-ring)_22%,transparent)]"
            : ""
        } ${className}`}
      >
        {selected?.icon && (
          <span aria-hidden="true" className="text-ink-3 flex shrink-0">
            {selected.icon}
          </span>
        )}
        <span
          className={`min-w-0 flex-1 truncate ${selected ? "" : "text-ink-3"} ${
            mono && selected?.value ? "font-mono text-[0.92em]" : ""
          }`}
        >
          {selected?.label ?? placeholder}
        </span>
        <ChevronDownIcon
          size={15}
          aria-hidden="true"
          className={`text-ink-3 shrink-0 transition-transform duration-150 ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open &&
        createPortal(
          phone ? (
            <div className="fixed inset-0 z-[60]">
              <div aria-hidden="true" className="animate-fade absolute inset-0 bg-black/40" />
              <div
                ref={popover}
                role="dialog"
                aria-modal="true"
                aria-label={name ?? "Choose an option"}
                onKeyDown={onKeyDown}
                className="bg-surface animate-sheet absolute inset-x-0 bottom-0 flex max-h-[80dvh] flex-col rounded-t-3xl pb-[env(safe-area-inset-bottom)] shadow-[0_-12px_40px_rgb(15_23_42/0.25)]"
              >
                <span
                  aria-hidden="true"
                  className="bg-line-strong mx-auto mt-2.5 h-1 w-10 rounded-full"
                />
                <div className="flex items-center justify-between gap-3 px-5 pt-3 pb-3">
                  <p className="text-ink text-base font-semibold">{name ?? "Choose"}</p>
                  <button
                    type="button"
                    aria-label="Close"
                    onClick={() => hide()}
                    className="text-ink-3 hover:bg-surface-3 focus-visible:outline-brand-ring -mr-2 flex size-10 items-center justify-center rounded-full focus-visible:outline-2"
                  >
                    <XIcon size={18} />
                  </button>
                </div>
                {searchField}
                {list}
              </div>
            </div>
          ) : (
            <div
              ref={popover}
              className={`bg-surface border-line shadow-lift animate-pop fixed z-[60] flex flex-col overflow-hidden rounded-xl border ${
                place?.bottom !== undefined ? "origin-bottom" : "origin-top"
              }`}
              style={
                place
                  ? { top: place.top, bottom: place.bottom, left: place.left, width: place.width }
                  : { visibility: "hidden" }
              }
            >
              {searchField}
              {list}
            </div>
          ),
          document.body,
        )}
    </>
  );
}

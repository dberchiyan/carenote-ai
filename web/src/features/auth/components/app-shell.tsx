"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { ApiError } from "@/shared/api/errors";
import type { Role } from "@/shared/api/types";
import { homeFor, ROLE_LABELS, useLogout, useMe } from "@/features/auth/hooks";

import {
  ChartIcon,
  ClipboardIcon,
  LockIcon,
  LogoMark,
  MicIcon,
  PanelLeftIcon,
  ShieldIcon,
  TargetIcon,
  WardIcon,
} from "@/shared/ui/icons";
import { ErrorState, Loading } from "@/shared/ui/states";
import { GuideMenu } from "@/features/guide/components/guide-menu";

import { UserMenu } from "./user-menu";

const NAV: { href: string; label: string; roles: Role[]; icon: ReactNode }[] = [
  { href: "/ward", label: "Ward", roles: ["nurse", "charge_nurse"], icon: <WardIcon /> },
  { href: "/notes/new", label: "Record note", roles: ["nurse", "charge_nurse"], icon: <MicIcon /> },
  {
    href: "/handover",
    label: "Handover",
    roles: ["nurse", "charge_nurse"],
    icon: <ClipboardIcon />,
  },
  {
    href: "/metrics",
    label: "LLM metrics",
    roles: ["charge_nurse", "auditor"],
    icon: <ChartIcon />,
  },
  {
    href: "/quality",
    label: "AI quality",
    roles: ["charge_nurse", "auditor"],
    icon: <TargetIcon />,
  },
  { href: "/audit", label: "Audit log", roles: ["auditor"], icon: <ShieldIcon /> },
];

const COLLAPSED_KEY = "carenote.nav-collapsed";

/** Desktop sidebar can fold into an icon rail; the choice is a per-browser convenience. */
function useCollapsedNav() {
  const [collapsed, setCollapsed] = useState(false);
  useEffect(() => {
    try {
      // Read after mount so server and first client render agree.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setCollapsed(localStorage.getItem(COLLAPSED_KEY) === "1");
    } catch {
      // Storage blocked (private mode): stay expanded.
    }
  }, []);
  const toggle = () =>
    setCollapsed((c) => {
      try {
        localStorage.setItem(COLLAPSED_KEY, c ? "0" : "1");
      } catch {
        // Not persisted; the toggle still works for this page view.
      }
      return !c;
    });
  return [collapsed, toggle] as const;
}

export function AppShell({ children }: { children: ReactNode }) {
  const me = useMe();
  const router = useRouter();
  const pathname = usePathname();
  const logout = useLogout();
  const [collapsed, toggleCollapsed] = useCollapsedNav();

  const unauthenticated = me.error instanceof ApiError && me.error.status === 401;
  useEffect(() => {
    if (unauthenticated) router.replace("/login");
  }, [unauthenticated, router]);

  if (me.isPending || unauthenticated) return <Loading />;
  if (me.isError) {
    return (
      <main className="mx-auto max-w-xl p-6">
        <ErrorState error={me.error} />
      </main>
    );
  }

  const user = me.data;
  const items = NAV.filter((item) => item.roles.includes(user.role));
  // Deny by default: a page reached by URL outside the role is refused up front, not left to
  // 403s from every request on it.
  const here = NAV.find((item) => pathname === item.href || pathname.startsWith(`${item.href}/`));
  const refused = here && !here.roles.includes(user.role);
  const signOut = () => logout.mutate(undefined, { onSettled: () => router.replace("/login") });

  return (
    <div className="flex min-h-full flex-col lg:flex-row">
      <a
        href="#main"
        className="focus:bg-surface focus:text-ink focus:shadow-lift sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-lg focus:px-3 focus:py-2"
      >
        Skip to content
      </a>

      {/* Sidebar on desktop. Phones and tablets get a bottom tab bar instead (below). */}
      <header
        className={`bg-nav text-nav-ink lg:border-nav-line z-30 hidden shrink-0 flex-col motion-reduce:transition-none lg:sticky lg:top-0 lg:flex lg:h-dvh lg:border-r lg:transition-[width] lg:duration-200 print:!hidden ${
          collapsed ? "lg:w-[76px]" : "lg:w-64"
        }`}
      >
        <div
          className={`flex items-center gap-2 px-4 py-3 lg:py-5 ${
            collapsed ? "lg:flex-col lg:gap-3 lg:px-0" : "lg:px-4"
          }`}
        >
          <Link
            href="/"
            className={`flex min-w-0 items-center gap-2.5 rounded-lg focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-teal-300 ${
              collapsed ? "" : "lg:pl-1"
            }`}
          >
            <LogoMark size={30} />
            <span
              className={`text-nav-ink-strong truncate text-[17px] font-semibold tracking-[-0.02em] ${
                collapsed ? "lg:hidden" : ""
              }`}
            >
              CareNote <span className="font-normal text-teal-300">AI</span>
            </span>
          </Link>
          <span className={`flex-1 ${collapsed ? "lg:hidden" : ""}`} />
          <button
            type="button"
            onClick={toggleCollapsed}
            aria-expanded={!collapsed}
            aria-label={collapsed ? "Expand menu" : "Collapse menu"}
            title={collapsed ? "Expand menu" : "Collapse menu"}
            className="text-nav-ink/70 hidden size-9 items-center justify-center rounded-lg hover:bg-white/[0.06] hover:text-white focus-visible:outline-2 focus-visible:outline-teal-300 lg:flex"
          >
            <PanelLeftIcon size={18} className={collapsed ? "-scale-x-100" : ""} />
          </button>
        </div>

        <nav
          aria-label="Main"
          className={`px-3 pb-3 lg:flex-1 lg:pb-0 ${collapsed ? "lg:px-3" : "lg:px-4"}`}
        >
          <p
            className={`text-nav-ink/70 mb-2 hidden px-3 text-[11px] font-semibold tracking-[0.08em] uppercase ${
              collapsed ? "" : "lg:block"
            }`}
          >
            Workspace
          </p>
          <ul className="flex gap-1 overflow-x-auto lg:flex-col">
            {items.map((item) => {
              const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    title={collapsed ? item.label : undefined}
                    className={`group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium whitespace-nowrap transition-colors focus-visible:outline-2 focus-visible:outline-teal-300 ${
                      collapsed ? "lg:justify-center" : ""
                    } ${
                      active
                        ? "bg-white/[0.07] text-white"
                        : "text-nav-ink hover:bg-white/[0.04] hover:text-white"
                    }`}
                  >
                    {active && (
                      <span
                        aria-hidden="true"
                        className="absolute inset-y-2 left-0 hidden w-0.5 rounded-full bg-teal-300 lg:block"
                      />
                    )}
                    <span className={active ? "text-teal-300" : "text-nav-ink/80"}>
                      {item.icon}
                    </span>
                    <span className={collapsed ? "lg:sr-only" : ""}>{item.label}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className={`hidden pb-5 lg:block ${collapsed ? "px-3" : "px-4"}`}>
          <div
            className={`border-nav-line bg-nav-2 text-nav-ink flex items-start gap-2.5 rounded-xl border px-3 py-3 text-xs leading-relaxed ${
              collapsed ? "justify-center px-0 py-2.5" : ""
            }`}
            title={
              collapsed
                ? "Names are redacted before AI. Nothing is saved until a nurse confirms."
                : undefined
            }
          >
            <LockIcon size={15} className="mt-0.5 shrink-0 text-teal-300" />
            <span className={collapsed ? "sr-only" : ""}>
              Names are redacted before AI. Nothing is saved until a nurse confirms.
            </span>
          </div>
        </div>
      </header>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Same container as <main>, so the badge and the account menu sit on the content's edges. */}
        <div className="border-line bg-surface sticky top-0 z-20 border-b print:hidden">
          <div className="mx-auto flex h-(--topbar) w-full max-w-[1560px] items-center justify-between gap-3 px-4 sm:px-5 lg:px-10">
            <Link
              href="/"
              aria-label="CareNote AI home"
              className="focus-visible:outline-brand-ring flex items-center gap-2 rounded-lg focus-visible:outline-2 lg:hidden"
            >
              <LogoMark size={28} />
              <span className="text-ink text-[15px] font-semibold tracking-[-0.02em]">
                CareNote <span className="text-brand-text font-normal">AI</span>
              </span>
            </Link>
            <p className="text-ink-2 flex items-center gap-2 text-xs font-medium">
              <span
                aria-hidden="true"
                className="bg-warn inline-block size-1.5 rounded-full shadow-[0_0_0_3px_color-mix(in_oklab,var(--warn)_25%,transparent)]"
              />
              <span className="hidden lg:inline">Demo environment — synthetic data only</span>
              <span className="hidden sm:inline lg:hidden">Demo · synthetic data</span>
              <span className="sr-only sm:hidden">Demo environment, synthetic data only</span>
            </p>
            <div className="flex items-center gap-1.5 sm:gap-2">
              <GuideMenu user={user} onSwitchRole={signOut} />
              <UserMenu user={user} onSignOut={signOut} />
            </div>
          </div>
        </div>
        <main
          id="main"
          className="mx-auto w-full max-w-[1560px] flex-1 px-4 pt-6 pb-[calc(5.5rem+env(safe-area-inset-bottom))] sm:px-5 sm:pt-8 lg:px-10 lg:py-10"
        >
          {refused ? (
            <div className="card mx-auto mt-10 max-w-lg px-8 py-10 text-center">
              <span className="bg-surface-3 text-ink-3 mx-auto mb-4 flex size-12 items-center justify-center rounded-2xl">
                <LockIcon />
              </span>
              <h1 className="text-ink text-xl font-semibold tracking-[-0.02em]">
                No access to this page
              </h1>
              <p className="text-ink-2 mt-2 text-sm leading-relaxed">
                {here.label} is for the{" "}
                {here.roles.map((r) => ROLE_LABELS[r].toLowerCase()).join(" and the ")}. You are
                signed in as {user.display_name} ({ROLE_LABELS[user.role].toLowerCase()}).
              </p>
              <Link
                href={homeFor(user)}
                className="text-brand-text focus-visible:outline-brand-ring mt-6 inline-block text-sm font-semibold underline-offset-4 hover:underline focus-visible:outline-2"
              >
                Back to your home page
              </Link>
            </div>
          ) : (
            <div key={pathname} className="animate-enter">
              {children}
            </div>
          )}
        </main>

        {/* Bottom tab bar: thumb reach on a phone, one tap to every area the role has. */}
        <nav
          aria-label="Main"
          className="border-line bg-surface/95 fixed inset-x-0 bottom-0 z-30 border-t pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden print:hidden"
        >
          <ul className="mx-auto flex max-w-xl items-stretch">
            {items.map((item) => {
              const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
              return (
                <li key={item.href} className="min-w-0 flex-1">
                  <Link
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    className={`focus-visible:outline-brand-ring flex min-h-14 flex-col items-center justify-center gap-1 px-1 text-[11px] font-medium focus-visible:outline-2 focus-visible:-outline-offset-2 ${
                      active ? "text-brand-text" : "text-ink-3 hover:text-ink"
                    }`}
                  >
                    <span
                      className={`flex h-7 w-12 items-center justify-center rounded-full transition-colors ${
                        active ? "bg-brand-soft" : ""
                      }`}
                    >
                      {item.icon}
                    </span>
                    <span className="truncate">{item.label}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      </div>
    </div>
  );
}

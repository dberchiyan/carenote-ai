"use client";

import { useRouter } from "next/navigation";
import type { ReactNode } from "react";

import { ServiceStatus } from "@/shared/layout/service-status";
import {
  ChevronRightIcon,
  FileIcon,
  LockIcon,
  LogoMark,
  MicIcon,
  ShieldIcon,
} from "@/shared/ui/icons";
import { ThemeToggle } from "@/shared/layout/theme-toggle";
import { ErrorState, Loading } from "@/shared/ui/states";
import { usePageTitle } from "@/shared/lib/use-page-title";
import type { User } from "@/shared/api/types";
import { homeFor, ROLE_LABELS, useDemoUsers, useLogin } from "@/features/auth/hooks";
import { initials } from "@/shared/lib/format";

const ROLE_DESCRIPTIONS: Record<User["role"], string> = {
  nurse: "Records voice notes, reviews AI drafts and confirms them.",
  charge_nurse: "Everything a nurse can do, plus the ward's LLM usage metrics.",
  auditor: "Read-only access to the audit log and usage metrics.",
};

const PRINCIPLES: { icon: ReactNode; title: string; text: string }[] = [
  {
    icon: <MicIcon size={17} />,
    title: "Speak at the bedside",
    text: "Vitals, symptoms and medications from one sentence.",
  },
  {
    icon: <LockIcon size={17} />,
    title: "Private by design",
    text: "Patients are matched locally; names never reach the AI.",
  },
  {
    icon: <ShieldIcon size={17} />,
    title: "The nurse decides",
    text: "Nothing becomes a record until it is confirmed — and audited.",
  },
  {
    icon: <FileIcon size={17} />,
    title: "Interoperable",
    text: "HL7 FHIR R4 with LOINC codes and UCUM units.",
  },
];

function Waveform() {
  const bars = [6, 14, 22, 12, 30, 18, 40, 26, 16, 34, 20, 10, 24, 38, 18, 28, 12, 20, 8, 14];
  return (
    <div aria-hidden="true" className="flex h-12 items-center gap-[5px]">
      {bars.map((h, i) => (
        <span
          key={i}
          className="animate-wave w-[3px] rounded-full bg-gradient-to-t from-teal-500/40 to-teal-300"
          style={{ height: h, animationDelay: `${(i % 7) * 120}ms` }}
        />
      ))}
    </div>
  );
}

export function LoginPage() {
  const users = useDemoUsers();
  const login = useLogin();
  usePageTitle("Sign in");
  const router = useRouter();

  return (
    <div className="grid min-h-dvh flex-1 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]">
      {/* On a phone the hero is one screen-third: the sign-in cards must be reachable without a hunt. */}
      <aside className="bg-nav text-nav-ink relative overflow-hidden px-6 py-7 sm:px-12 sm:py-10 lg:px-16 lg:py-14">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -top-40 -right-40 size-[34rem] rounded-full bg-teal-500/15 blur-3xl"
        />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 [background-image:linear-gradient(to_right,#fff_1px,transparent_1px),linear-gradient(to_bottom,#fff_1px,transparent_1px)] [mask-image:radial-gradient(ellipse_at_top_left,black,transparent_70%)] [background-size:44px_44px] opacity-[0.07]"
        />
        <div className="relative flex h-full flex-col">
          <div className="flex items-center gap-2.5">
            <LogoMark size={34} />
            <span className="text-lg font-semibold tracking-[-0.02em] text-white">
              CareNote <span className="font-normal text-teal-300">AI</span>
            </span>
          </div>

          <div className="mt-7 max-w-xl sm:mt-14 lg:mt-auto">
            <p className="mb-5 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs font-medium text-teal-200">
              Clinical voice documentation
            </p>
            <p className="text-[1.875rem] leading-[1.08] font-semibold tracking-[-0.04em] text-white sm:text-[3.25rem]">
              Documentation that keeps pace with <span className="text-teal-300">care.</span>
            </p>
            <p className="text-nav-ink mt-3 max-w-md text-[15px] leading-relaxed sm:mt-5">
              Say the note at the bedside. Review a structured draft in seconds. Confirm — and it is
              in the chart.
            </p>
            <div className="mt-5 hidden sm:mt-8 sm:block">
              <Waveform />
            </div>
          </div>

          <ul className="mt-12 hidden gap-x-8 gap-y-6 sm:grid sm:grid-cols-2 lg:mt-auto lg:pt-14">
            {PRINCIPLES.map((p) => (
              <li key={p.title} className="flex gap-3">
                <span className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-white/10 bg-white/5 text-teal-300">
                  {p.icon}
                </span>
                <span>
                  <span className="block text-sm font-semibold text-white">{p.title}</span>
                  <span className="text-nav-ink mt-0.5 block text-[13px] leading-snug">
                    {p.text}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      </aside>

      <main className="bg-canvas relative flex flex-col justify-center px-5 pt-16 pb-10 sm:px-12 sm:py-12 lg:px-16">
        <div className="absolute top-4 right-4 sm:top-5 sm:right-5">
          <ThemeToggle />
        </div>
        <div className="mx-auto w-full max-w-md">
          <h1 className="text-ink text-[1.75rem] font-semibold tracking-[-0.03em]">CareNote AI</h1>
          <p className="text-ink-2 mt-2 text-[15px]">
            Choose a demo user to sign in. Each role sees a different part of the product.
          </p>

          <div className="mt-8 flex flex-col gap-3">
            {users.isPending && <Loading label="Loading demo users…" />}
            {users.isError && <ErrorState error={users.error} />}
            {users.data?.length === 0 && (
              <ErrorState error={new Error("No demo users found. Run `make seed` first.")} />
            )}
            {users.data && users.data.length > 0 && (
              <ul className="flex flex-col gap-3">
                {users.data.map((user) => (
                  <li key={user.id}>
                    <button
                      type="button"
                      disabled={login.isPending}
                      onClick={() =>
                        login.mutate(user.username, {
                          onSuccess: (u) => router.replace(homeFor(u)),
                        })
                      }
                      className="group card hover:border-brand/40 hover:shadow-lift focus-visible:outline-brand-ring flex w-full items-center gap-4 p-4 text-left transition-[box-shadow,border-color,transform] duration-200 hover:-translate-y-px focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-60 motion-reduce:hover:translate-y-0"
                    >
                      <span
                        aria-hidden="true"
                        className="bg-brand-soft text-brand-text ring-brand/15 flex size-11 shrink-0 items-center justify-center rounded-full text-sm font-semibold ring-1"
                      >
                        {initials(user.display_name)}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="flex flex-wrap items-baseline gap-x-2">
                          <span className="text-brand-text text-xs font-semibold tracking-[0.06em] uppercase">
                            {ROLE_LABELS[user.role]}
                          </span>
                          <span className="text-ink-3 text-xs">
                            {user.ward ? `Ward ${user.ward}` : "All wards"}
                          </span>
                        </span>
                        <span className="text-ink mt-0.5 block font-semibold">
                          {user.display_name}
                        </span>
                        <span className="text-ink-3 mt-0.5 block text-[13px] leading-snug">
                          {ROLE_DESCRIPTIONS[user.role]}
                        </span>
                      </span>
                      <ChevronRightIcon className="text-ink-3 group-hover:text-brand-text shrink-0 transition-transform group-hover:translate-x-0.5" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {login.isError && <ErrorState error={login.error} />}
          </div>

          <div
            role="note"
            className="border-warn-line bg-warn-soft text-warn-fg mt-8 rounded-xl border px-4 py-3 text-[13px] leading-relaxed"
          >
            <strong className="font-semibold">Demo application — synthetic data only.</strong> Never
            enter real patient information. Not a medical device; no clinical advice.
          </div>
          <div className="text-ink-3 mt-6 text-sm">
            <ServiceStatus />
          </div>
        </div>
      </main>
    </div>
  );
}

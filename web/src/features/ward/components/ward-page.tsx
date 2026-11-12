"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";

import { buttonClass } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import { StatCard } from "@/shared/ui/stat";
import { AlertIcon, ClockIcon, FileIcon, MicIcon, SearchIcon, UsersIcon } from "@/shared/ui/icons";
import { SearchInput } from "@/shared/ui/field";
import { StatCardsSkeleton, SkeletonStatus, TableSkeleton } from "@/shared/ui/skeleton";
import { EmptyState, ErrorState, PageHeader } from "@/shared/ui/states";
import { useMe } from "@/features/auth/hooks";
import { useNotes } from "@/features/notes/hooks";
import { usePatients } from "@/features/ward/hooks";
import { usePageTitle } from "@/shared/lib/use-page-title";
import { useUrlState } from "@/shared/lib/use-url-state";
import { FLAG_META } from "@/shared/lib/vitals";

import { PatientCard, PatientRow } from "./patient-row";
import { NoteItem } from "./recent-notes";

export function WardPage() {
  const me = useMe();
  const patients = usePatients();
  const notes = useNotes();
  const [params, setParams] = useUrlState();
  const query = params.get("q") ?? "";
  const flaggedOnly = params.get("flagged") === "1";
  const setQuery = (q: string) => setParams({ q });
  const setFlaggedOnly = (on: boolean) => setParams({ flagged: on ? "1" : null });
  const searchRef = useRef<HTMLInputElement>(null);
  usePageTitle(me.data?.ward ? `Ward ${me.data.ward}` : "Ward");
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const typing = target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName);
      if (e.key === "/" && !typing && !e.metaKey && !e.ctrlKey) {
        e.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  const names = new Map(patients.data?.map((p) => [p.id, `${p.family_name}, ${p.given_name}`]));
  const recent = notes.data?.slice(0, 6) ?? [];

  const list = patients.data ?? [];
  const attention = list.filter((p) => p.latest_vitals.some((v) => v.flag !== "normal")).length;
  const critical = list.filter((p) => p.latest_vitals.some((v) => v.flag === "critical")).length;
  const drafts = list.reduce((sum, p) => sum + p.open_drafts, 0);
  const needle = query.trim().toLowerCase();
  const shown = list.filter(
    (p) =>
      (!flaggedOnly || p.latest_vitals.some((v) => v.flag !== "normal")) &&
      (!needle ||
        `${p.family_name}, ${p.given_name} ${p.given_name} ${p.family_name} ${p.room} ${p.mrn}`
          .toLowerCase()
          .includes(needle)),
  );
  const today = new Date().toDateString();
  const notesToday = (notes.data ?? []).filter(
    (n) => new Date(n.created_at).toDateString() === today,
  ).length;

  return (
    <>
      <PageHeader
        eyebrow={new Date().toLocaleDateString(undefined, {
          weekday: "long",
          month: "long",
          day: "numeric",
        })}
        title={`Ward ${me.data?.ward ?? ""}`}
        subtitle="Latest confirmed vitals. Flags follow the ward's alert rules."
        actions={
          // On phones the tab bar already offers Record; the header stays focused on the ward.
          <span className="hidden sm:block">
            <Link href="/notes/new" className={buttonClass("primary")}>
              <MicIcon size={17} />
              Record note
            </Link>
          </span>
        }
      />

      {patients.isPending && (
        <SkeletonStatus label="Loading patients…">
          <StatCardsSkeleton />
          <TableSkeleton rows={8} />
        </SkeletonStatus>
      )}
      {patients.data && (
        <section
          aria-label="Ward summary"
          className="mb-6 grid grid-cols-2 gap-3 sm:mb-8 sm:gap-4 xl:grid-cols-4"
        >
          <StatCard
            icon={<UsersIcon size={16} />}
            label="Patients"
            value={list.length}
            hint="On your ward list"
          />
          <StatCard
            icon={<AlertIcon size={16} />}
            label="Flagged vitals"
            value={attention}
            hint={critical ? `${critical} with a critical value` : "Warning or critical"}
            tone={attention ? "attention" : "neutral"}
          />
          <StatCard
            icon={<FileIcon size={16} />}
            label="Drafts to review"
            value={drafts}
            hint="Waiting for a nurse"
          />
          <StatCard
            icon={<ClockIcon size={16} />}
            label="Notes today"
            value={notesToday}
            hint={me.data?.role === "charge_nurse" ? "Across the ward" : "Recorded by you"}
          />
        </section>
      )}

      <div className="grid gap-6 2xl:grid-cols-[minmax(0,1fr)_340px]">
        <section aria-labelledby="patients-heading" className="min-w-0">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <h2 id="patients-heading" className="text-lg font-semibold tracking-[-0.01em]">
              Patients
              {patients.data && (
                <span className="text-ink-3 ml-2 text-sm font-normal tabular-nums">
                  {shown.length === list.length ? list.length : `${shown.length} of ${list.length}`}
                </span>
              )}
            </h2>
            {patients.data && patients.data.length > 0 && (
              <div className="flex w-full items-center gap-2 sm:w-auto">
                <SearchInput
                  ref={searchRef}
                  aria-label="Search patients"
                  value={query}
                  onChange={setQuery}
                  placeholder="Name, room or MRN"
                  shortcut="/"
                  size="sm"
                  className="w-full sm:w-56"
                />
                <button
                  type="button"
                  aria-pressed={flaggedOnly}
                  onClick={() => setFlaggedOnly(!flaggedOnly)}
                  className={`flex h-10 shrink-0 items-center gap-1.5 rounded-lg px-3 text-sm font-medium ring-1 transition-colors ring-inset focus-visible:outline-2 sm:h-9 ${
                    flaggedOnly
                      ? "bg-amber-50 text-amber-900 ring-amber-400/60 dark:bg-amber-950/50 dark:text-amber-100 dark:ring-amber-500/40"
                      : "bg-surface text-ink-2 ring-line-strong hover:bg-surface-2"
                  } focus-visible:outline-brand-ring`}
                >
                  <AlertIcon size={14} />
                  Flagged only
                </button>
              </div>
            )}
          </div>
          {patients.isError && <ErrorState error={patients.error} />}
          {patients.data?.length === 0 && (
            <EmptyState icon={<UsersIcon />} title="No patients on this ward." />
          )}
          {patients.data && patients.data.length > 0 && shown.length === 0 && (
            <EmptyState icon={<SearchIcon />} title="No patients match.">
              Try another name or room, or clear the filter.
            </EmptyState>
          )}
          {patients.data && shown.length > 0 && (
            <ul className="flex flex-col gap-2 md:hidden" aria-label="Patients">
              {shown.map((p) => (
                <PatientCard key={p.id} p={p} />
              ))}
            </ul>
          )}
          {patients.data && shown.length > 0 && (
            <Card className="hidden overflow-x-auto md:block">
              <table className="w-full min-w-[720px] text-left text-sm">
                <caption className="sr-only">
                  Patients on the ward with latest vitals. Flags: {FLAG_META.warning.label},{" "}
                  {FLAG_META.critical.label}.
                </caption>
                <thead className="border-line bg-surface-2 text-ink-3 border-b text-xs">
                  <tr>
                    <th scope="col" className="py-3 pr-3 pl-5 font-medium">
                      Room
                    </th>
                    <th scope="col" className="px-3 py-3 font-medium">
                      Patient
                    </th>
                    <th scope="col" className="px-3 py-3 font-medium">
                      Status
                    </th>
                    <th scope="col" className="px-3 py-3 font-medium">
                      Latest vitals
                    </th>
                    <th scope="col" className="py-3 pr-5 pl-3 text-right font-medium">
                      Drafts
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {shown.map((p) => (
                    <PatientRow key={p.id} p={p} />
                  ))}
                </tbody>
              </table>
            </Card>
          )}
        </section>

        <section aria-labelledby="recent-heading" className="min-w-0 md:order-first 2xl:order-none">
          <div className="mb-3 flex items-baseline justify-between">
            <h2 id="recent-heading" className="text-lg font-semibold tracking-[-0.01em]">
              {me.data?.role === "charge_nurse" ? "Recent notes on the ward" : "Your recent notes"}
            </h2>
          </div>
          <Card className="p-2 2xl:sticky 2xl:top-6">
            {recent.length > 0 ? (
              <ul className="grid gap-x-2 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-1">
                {recent.slice(0, 4).map((n) => (
                  <NoteItem
                    key={n.id}
                    n={n}
                    name={
                      n.patient_id ? (names.get(n.patient_id) ?? "Patient") : "Patient not selected"
                    }
                  />
                ))}
              </ul>
            ) : (
              <div className="px-4 py-10 text-center">
                <p className="text-ink text-sm font-semibold">No notes yet</p>
                <p className="text-ink-3 mt-1 text-sm">Record your first note at the bedside.</p>
              </div>
            )}
          </Card>
        </section>
      </div>
    </>
  );
}

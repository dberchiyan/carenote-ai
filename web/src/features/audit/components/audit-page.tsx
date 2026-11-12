"use client";

import { Fragment, useState } from "react";

import { Card } from "@/shared/ui/card";
import { Field, Input, Select, type SelectOption } from "@/shared/ui/field";
import { ChevronRightIcon, CopyIcon } from "@/shared/ui/icons";
import { SkeletonStatus, TableSkeleton } from "@/shared/ui/skeleton";
import { Pagination } from "@/shared/ui/pagination";
import { EmptyState, ErrorState, PageHeader } from "@/shared/ui/states";
import { useToast } from "@/shared/ui/toast";
import type { AuditEvent } from "@/shared/api/types";
import { formatDateTime, formatRelative } from "@/shared/lib/format";
import { useUrlState } from "@/shared/lib/use-url-state";
import { useAuditActions, useAuditEvents } from "@/features/audit/hooks";
import { markGuideStep } from "@/features/guide/hooks";
import { usePageTitle } from "@/shared/lib/use-page-title";

const ENTITIES: SelectOption[] = [
  { value: "", label: "All entities" },
  { value: "note", label: "Note" },
  { value: "patient", label: "Patient" },
  { value: "user", label: "User" },
  { value: "audit", label: "Audit" },
  { value: "eval_cases", label: "Eval cases" },
];

const FAMILIES: Record<string, string> = {
  auth: "Sign-in",
  note: "Notes",
  fhir: "Export",
  quality: "AI quality",
  audit: "Audit log",
};

const DESCRIPTIONS: Record<string, string> = {
  "auth.login": "Signed in",
  "auth.logout": "Signed out",
  "note.upload": "Recording uploaded",
  "note.create": "Typed note created",
  "note.draft_edit": "Draft corrected by a nurse",
  "note.confirm": "Draft confirmed into the record",
  "note.reject": "Draft rejected",
  "note.retry": "Processing retried",
  "fhir.export": "FHIR bundle downloaded",
  "quality.corrections_export": "Corrections exported as eval cases",
  "audit.view": "Audit log viewed",
};

/** An action as a dropdown option: grouped by family, with what it means underneath. */
function actionOption(action: string): SelectOption {
  const family = action.split(".")[0] ?? action;
  return {
    value: action,
    label: action,
    description: DESCRIPTIONS[action],
    group: FAMILIES[family] ?? "Other",
  };
}

/** Tone per action family, with the action name itself always visible. */
function actionTone(action: string): string {
  if (action.endsWith(".confirm")) return "bg-ok-soft text-ok-fg ring-ok-line";
  if (action.endsWith(".reject")) return "bg-bad-soft text-bad-fg ring-bad-line";
  if (action.startsWith("fhir.") || action.endsWith("_export"))
    return "bg-brand-soft text-brand-text ring-brand/25";
  if (action.startsWith("note.")) return "bg-info-soft text-info-fg ring-info-line";
  return "bg-surface-3 text-ink-2 ring-line";
}

type Json = Record<string, unknown>;

function hasChange(event: AuditEvent): boolean {
  return !!event.before || !!event.after;
}

function show(value: unknown): string {
  if (value === undefined) return "—";
  if (value === null) return "null";
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2);
}

/**
 * Before and after, field by field: what changed is highlighted, unchanged fields are listed
 * quietly underneath. Long values wrap inside their column instead of widening the table.
 */
function ChangeView({ event }: { event: AuditEvent }) {
  const before = (event.before ?? null) as Json | null;
  const after = (event.after ?? null) as Json | null;
  const keys = [...new Set([...Object.keys(before ?? {}), ...Object.keys(after ?? {})])];
  const both = !!before && !!after;
  const rows = keys
    .map((key) => {
      const was = before?.[key];
      const now = after?.[key];
      return { key, was, now, changed: both && JSON.stringify(was) !== JSON.stringify(now) };
    })
    .sort((a, b) => Number(b.changed) - Number(a.changed));
  const changed = rows.filter((r) => r.changed).length;

  return (
    <div className="bg-surface-2 ring-line overflow-hidden rounded-xl ring-1">
      <div className="border-line text-ink-3 flex flex-wrap items-center gap-x-3 gap-y-1 border-b px-4 py-2.5 text-xs">
        <span className="text-ink font-semibold">
          {both ? `${changed} of ${rows.length} fields changed` : `${rows.length} fields recorded`}
        </span>
        {both && (
          <span className="flex items-center gap-1.5">
            <span aria-hidden="true" className="bg-warn size-2 rounded-full" /> changed
          </span>
        )}
      </div>
      <div
        role="table"
        aria-label="Recorded change"
        className="divide-line max-h-[28rem] divide-y overflow-y-auto"
      >
        <div
          role="row"
          className={`text-ink-3 grid gap-4 px-4 py-2 text-[11px] font-semibold tracking-[0.06em] uppercase ${
            both ? "grid-cols-[minmax(7rem,12rem)_1fr_1fr]" : "grid-cols-[minmax(7rem,12rem)_1fr]"
          }`}
        >
          <span role="columnheader">Field</span>
          {before && <span role="columnheader">{both ? "Before" : "Value"}</span>}
          {after && <span role="columnheader">{both ? "After" : "Value"}</span>}
        </div>
        {rows.map((r) => (
          <div
            key={r.key}
            role="row"
            className={`grid items-start gap-4 px-4 py-2 text-xs ${
              both ? "grid-cols-[minmax(7rem,12rem)_1fr_1fr]" : "grid-cols-[minmax(7rem,12rem)_1fr]"
            } ${r.changed ? "bg-warn-soft/60" : ""}`}
          >
            <span
              role="cell"
              className="text-ink flex items-center gap-2 font-mono font-medium break-all"
            >
              {r.changed && (
                <span aria-hidden="true" className="bg-warn size-2 shrink-0 rounded-full" />
              )}
              {r.key}
              {r.changed && <span className="sr-only">(changed)</span>}
            </span>
            {before && (
              <pre
                role="cell"
                className={`font-mono break-words whitespace-pre-wrap ${
                  r.changed ? "text-ink-2 decoration-bad/60 line-through" : "text-ink-2"
                }`}
              >
                {show(r.was)}
              </pre>
            )}
            {after && (
              <pre
                role="cell"
                className={`font-mono break-words whitespace-pre-wrap ${
                  r.changed ? "text-ink font-semibold" : "text-ink-2"
                }`}
              >
                {show(r.now)}
              </pre>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function ChangeToggle({
  event,
  open,
  onToggle,
  controls,
}: {
  event: AuditEvent;
  open: boolean;
  onToggle: () => void;
  controls: string;
}) {
  if (!hasChange(event)) return <span className="text-ink-3">—</span>;
  return (
    <button
      type="button"
      aria-expanded={open}
      aria-controls={controls}
      onClick={onToggle}
      className="text-brand-text focus-visible:outline-brand-ring inline-flex items-center gap-1 rounded-md text-sm font-medium whitespace-nowrap hover:underline focus-visible:outline-2"
    >
      <ChevronRightIcon
        size={14}
        aria-hidden="true"
        className={`transition-transform duration-150 ${open ? "rotate-90" : ""}`}
      />
      {open ? "Hide change" : "View change"}
    </button>
  );
}

export function AuditPage() {
  // Filters and the page live in the URL: a view can be reloaded, shared or returned to.
  const [params, setParams] = useUrlState();
  const entity = params.get("entity") ?? "";
  const entityId = params.get("entity_id") ?? "";
  const action = params.get("action") ?? "";
  const offset = Number(params.get("offset") ?? 0) || 0;
  const events = useAuditEvents({ entity, entity_id: entityId.trim(), action }, offset);
  const actions = useAuditActions();
  // One change open at a time, shown full width under its row so the columns never move.
  const [openId, setOpenId] = useState<string | null>(null);
  const toggle = (id: string) => {
    if (openId !== id) markGuideStep("audit-change-opened");
    setOpenId((current) => (current === id ? null : id));
  };
  const filter = (next: { entity?: string; entityId?: string; action?: string }) =>
    setParams({ entity: next.entity, entity_id: next.entityId, action: next.action, offset: null });
  const setOffset = (value: number) => setParams({ offset: value });
  const toast = useToast();
  usePageTitle("Audit log");

  async function copyId(id: string) {
    try {
      await navigator.clipboard.writeText(id);
      toast({ title: "ID copied", description: id, tone: "info" });
    } catch {
      toast({ title: "Could not copy", description: id, tone: "danger" });
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Compliance"
        title="Audit log"
        subtitle="Append-only record of logins, uploads, edits, confirmations, exports and audit views."
      />
      <form
        className="card mb-5 grid grid-cols-2 items-end gap-3 p-4 sm:flex sm:flex-wrap sm:gap-4"
        onSubmit={(e) => e.preventDefault()}
        aria-label="Filters"
      >
        <Field label="Entity" className="sm:min-w-44">
          {({ id }) => (
            <Select
              id={id}
              size="sm"
              title="Entity"
              value={entity}
              onChange={(v) => filter({ entity: v })}
              options={ENTITIES}
            />
          )}
        </Field>
        <Field label="Action" className="sm:min-w-44">
          {({ id }) => (
            <Select
              id={id}
              size="sm"
              title="Action"
              mono
              searchPlaceholder="Search actions"
              value={action}
              onChange={(v) => filter({ action: v })}
              options={[
                { value: "", label: "All actions" },
                ...(actions.data ?? (action ? [action] : [])).map(actionOption),
              ]}
            />
          )}
        </Field>
        <Field label="Entity ID" className="col-span-2 sm:min-w-72 sm:flex-1">
          {({ id }) => (
            <Input
              id={id}
              className="font-mono"
              placeholder="UUID"
              value={entityId}
              onChange={(e) => filter({ entityId: e.target.value })}
            />
          )}
        </Field>
      </form>

      {events.isPending && (
        <SkeletonStatus label="Loading audit events…">
          <TableSkeleton rows={8} columns={5} />
        </SkeletonStatus>
      )}
      {events.isError && <ErrorState error={events.error} />}
      {events.data?.total === 0 && <EmptyState title="No matching events." />}
      {events.data && events.data.items.length > 0 && (
        <ul
          className="flex flex-col gap-2 md:hidden"
          aria-label="Audit events"
          aria-busy={events.isPlaceholderData}
        >
          {events.data.items.map((e) => (
            <li key={e.id} className="card p-3.5">
              <div className="flex items-start justify-between gap-2">
                <span
                  className={`rounded-md px-2 py-1 font-mono text-xs ring-1 ring-inset ${actionTone(e.action)}`}
                >
                  {e.action}
                </span>
                <time
                  dateTime={e.at}
                  title={formatDateTime(e.at)}
                  className="text-ink-3 shrink-0 text-xs"
                >
                  {formatRelative(e.at)}
                </time>
              </div>
              <p className="text-ink mt-2 text-sm font-medium">{e.actor_name ?? "system"}</p>
              <p className="text-ink-3 flex items-center gap-1 text-xs">
                {e.entity}
                {e.entity_id && (
                  <button
                    type="button"
                    title={`Filter by ${e.entity_id}`}
                    onClick={() => filter({ entity: e.entity, entityId: e.entity_id ?? "" })}
                    className="text-brand-text font-mono hover:underline"
                  >
                    {e.entity_id.slice(0, 8)}…
                  </button>
                )}
              </p>
              <div className="mt-2 text-sm">
                <ChangeToggle
                  event={e}
                  open={openId === e.id}
                  onToggle={() => toggle(e.id)}
                  controls={`change-m-${e.id}`}
                />
              </div>
              {openId === e.id && (
                <div id={`change-m-${e.id}`} className="mt-3">
                  <ChangeView event={e} />
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
      {events.data && events.data.items.length > 0 && (
        <Card className="hidden overflow-x-auto md:block" aria-busy={events.isPlaceholderData}>
          <table className="w-full min-w-[760px] table-fixed text-left text-sm">
            <colgroup>
              {/* Shares of the width, so the columns spread evenly at any screen size. */}
              <col className="w-[20%]" />
              <col className="w-[19%]" />
              <col className="w-[23%]" />
              <col className="w-[20%]" />
              <col className="w-[18%]" />
            </colgroup>
            <thead className="border-line bg-surface-2 text-ink-3 border-b text-xs">
              <tr>
                <th scope="col" className="px-5 py-3 font-medium">
                  Time
                </th>
                <th scope="col" className="px-5 py-3 font-medium">
                  Actor
                </th>
                <th scope="col" className="px-5 py-3 font-medium">
                  Action
                </th>
                <th scope="col" className="px-5 py-3 font-medium">
                  Entity
                </th>
                <th scope="col" className="px-5 py-3 font-medium">
                  Details
                </th>
              </tr>
            </thead>
            <tbody>
              {events.data.items.map((e) => (
                <Fragment key={e.id}>
                  <tr
                    className={`border-line hover:bg-surface-2 align-top ${
                      openId === e.id ? "bg-surface-2" : "border-b"
                    }`}
                  >
                    <td className="px-5 py-3 whitespace-nowrap">
                      <time dateTime={e.at} title={formatDateTime(e.at)} className="text-ink block">
                        {formatRelative(e.at)}
                      </time>
                      <span className="text-ink-3 block text-xs tabular-nums">
                        {formatDateTime(e.at)}
                      </span>
                    </td>
                    <td className="truncate px-5 py-3 font-medium">{e.actor_name ?? "system"}</td>
                    <td className="px-5 py-3">
                      <span
                        className={`rounded-md px-2 py-1 font-mono text-xs ring-1 ring-inset ${actionTone(e.action)}`}
                      >
                        {e.action}
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      {e.entity}
                      {e.entity_id && (
                        <span className="flex items-center gap-1">
                          <button
                            type="button"
                            title={`Filter by ${e.entity_id}`}
                            onClick={() =>
                              filter({ entity: e.entity, entityId: e.entity_id ?? "" })
                            }
                            className="text-brand-text font-mono text-xs hover:underline"
                          >
                            {e.entity_id.slice(0, 8)}…
                          </button>
                          <button
                            type="button"
                            aria-label={`Copy ID ${e.entity_id}`}
                            title="Copy ID"
                            onClick={() => void copyId(e.entity_id ?? "")}
                            className="text-ink-3 hover:bg-surface-3 hover:text-ink focus-visible:outline-brand-ring flex size-6 items-center justify-center rounded-md focus-visible:outline-2"
                          >
                            <CopyIcon size={13} />
                          </button>
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-3">
                      <ChangeToggle
                        event={e}
                        open={openId === e.id}
                        onToggle={() => toggle(e.id)}
                        controls={`change-${e.id}`}
                      />
                    </td>
                  </tr>
                  {openId === e.id && (
                    <tr id={`change-${e.id}`} className="border-line bg-surface-2 border-b">
                      <td colSpan={5} className="px-5 pt-1 pb-4">
                        <ChangeView event={e} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </Card>
      )}
      {events.data && <Pagination page={events.data} onOffset={setOffset} label="events" />}
    </>
  );
}

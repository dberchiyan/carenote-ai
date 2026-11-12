"use client";

import { Card } from "@/shared/ui/card";
import { Field, Input, Select } from "@/shared/ui/field";
import { CopyIcon } from "@/shared/ui/icons";
import { SkeletonStatus, TableSkeleton } from "@/shared/ui/skeleton";
import { Pagination } from "@/shared/ui/pagination";
import { EmptyState, ErrorState, PageHeader } from "@/shared/ui/states";
import { useToast } from "@/shared/ui/toast";
import type { AuditEvent } from "@/shared/api/types";
import { formatDateTime, formatRelative } from "@/shared/lib/format";
import { useUrlState } from "@/shared/lib/use-url-state";
import { useAuditActions, useAuditEvents } from "@/features/audit/hooks";
import { usePageTitle } from "@/shared/lib/use-page-title";

/** Tone per action family, with the action name itself always visible. */
function actionTone(action: string): string {
  if (action.endsWith(".confirm"))
    return "bg-emerald-50 text-emerald-900 ring-emerald-600/25 dark:bg-emerald-950/60 dark:text-emerald-100 dark:ring-emerald-400/25";
  if (action.endsWith(".reject"))
    return "bg-red-50 text-red-900 ring-red-600/25 dark:bg-red-950/60 dark:text-red-100 dark:ring-red-400/25";
  if (action.startsWith("fhir.") || action.endsWith("_export"))
    return "bg-brand-soft text-brand-text ring-brand/25";
  if (action.startsWith("note."))
    return "bg-sky-50 text-sky-900 ring-sky-600/25 dark:bg-sky-950/60 dark:text-sky-100 dark:ring-sky-400/25";
  return "bg-surface-3 text-ink-2 ring-line";
}

function Details({ event }: { event: AuditEvent }) {
  if (!event.before && !event.after) return <span className="text-ink-3">—</span>;
  return (
    <details>
      <summary className="text-brand-text cursor-pointer hover:underline">View change</summary>
      <div className="mt-2 grid gap-2 md:grid-cols-2">
        {event.before && (
          <pre className="bg-surface-2 ring-line max-h-64 overflow-auto rounded-lg p-3 text-xs ring-1">
            <strong>before</strong>
            {"\n"}
            {JSON.stringify(event.before, null, 2)}
          </pre>
        )}
        {event.after && (
          <pre className="bg-surface-2 ring-line max-h-64 overflow-auto rounded-lg p-3 text-xs ring-1">
            <strong>after</strong>
            {"\n"}
            {JSON.stringify(event.after, null, 2)}
          </pre>
        )}
      </div>
    </details>
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
        className="card mb-5 flex flex-wrap items-end gap-4 p-4"
        onSubmit={(e) => e.preventDefault()}
        aria-label="Filters"
      >
        <Field label="Entity" className="min-w-44">
          {({ id }) => (
            <Select id={id} value={entity} onChange={(e) => filter({ entity: e.target.value })}>
              <option value="">All</option>
              <option value="note">Note</option>
              <option value="patient">Patient</option>
              <option value="user">User</option>
              <option value="audit">Audit</option>
            </Select>
          )}
        </Field>
        <Field label="Action" className="min-w-44">
          {({ id }) => (
            <Select id={id} value={action} onChange={(e) => filter({ action: e.target.value })}>
              <option value="">All</option>
              {(actions.data ?? (action ? [action] : [])).map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Entity ID" className="min-w-72 flex-1">
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
        <Card className="overflow-x-auto" aria-busy={events.isPlaceholderData}>
          <table className="w-full min-w-[720px] text-left text-sm">
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
                <tr
                  key={e.id}
                  className="border-line hover:bg-surface-2 border-b align-top last:border-0"
                >
                  <td className="px-5 py-3 whitespace-nowrap">
                    <time dateTime={e.at} title={formatDateTime(e.at)} className="text-ink block">
                      {formatRelative(e.at)}
                    </time>
                    <span className="text-ink-3 block text-xs tabular-nums">
                      {formatDateTime(e.at)}
                    </span>
                  </td>
                  <td className="px-5 py-3 font-medium">{e.actor_name ?? "system"}</td>
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
                          onClick={() => filter({ entity: e.entity, entityId: e.entity_id ?? "" })}
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
                    <Details event={e} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
      {events.data && <Pagination page={events.data} onOffset={setOffset} label="events" />}
    </>
  );
}

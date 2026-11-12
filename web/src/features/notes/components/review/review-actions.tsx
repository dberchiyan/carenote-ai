import { useState } from "react";

import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/field";
import { CheckIcon } from "@/shared/ui/icons";

/** The sticky bar: reject (with an optional reason), save changes, confirm. */
export function ReviewActions({
  busy,
  dirty,
  invalid,
  patientSelected,
  saving,
  confirming,
  onSave,
  onConfirm,
  onReject,
}: {
  busy: boolean;
  dirty: boolean;
  invalid: boolean;
  patientSelected: boolean;
  saving: boolean;
  confirming: boolean;
  onSave: () => void;
  onConfirm: () => void;
  onReject: (reason: string | null) => void;
}) {
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  return (
    <div className="border-line bg-surface/90 shadow-lift sticky bottom-4 z-10 flex flex-wrap items-center gap-3 rounded-2xl border px-4 py-3 backdrop-blur-md">
      {rejecting ? (
        <form
          className="flex flex-1 flex-wrap items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            onReject(reason.trim() || null);
          }}
        >
          <Input
            aria-label="Reason for rejecting"
            placeholder="Reason (optional)"
            className="max-w-xs"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <Button type="submit" variant="danger" disabled={busy}>
            Reject note
          </Button>
          <Button variant="ghost" onClick={() => setRejecting(false)}>
            Cancel
          </Button>
        </form>
      ) : (
        <>
          <Button variant="ghost" onClick={() => setRejecting(true)} disabled={busy}>
            Reject
          </Button>
          <span className="flex-1" />
          {(!patientSelected || invalid) && (
            <span id="confirm-hint" className="text-ink-3 text-sm">
              {!patientSelected
                ? "Select the patient to enable Confirm."
                : "Enter a value for every vital sign, or remove the empty row."}
            </span>
          )}
          {dirty && (
            <Button variant="secondary" disabled={busy || invalid} onClick={onSave}>
              {saving ? "Saving…" : "Save changes"}
            </Button>
          )}
          <Button
            onClick={onConfirm}
            disabled={!patientSelected || busy || invalid}
            aria-describedby="confirm-hint"
            className="px-6"
          >
            <CheckIcon size={17} />
            {confirming ? "Confirming…" : "Confirm"}
          </Button>
        </>
      )}
    </div>
  );
}

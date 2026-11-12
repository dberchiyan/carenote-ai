"use client";

import { useParams } from "next/navigation";
import { useEffect, useRef } from "react";

import { DraftReview } from "@/features/notes/components/draft-review";
import { PipelineStatus } from "@/features/notes/components/pipeline-status";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import { CardSkeleton, Skeleton, SkeletonStatus } from "@/shared/ui/skeleton";
import { ErrorState, PageHeader } from "@/shared/ui/states";
import { useToast } from "@/shared/ui/toast";
import { formatDateTime } from "@/shared/lib/format";
import { isProcessing, useNote, useRetry } from "@/features/notes/hooks";
import { usePageTitle } from "@/shared/lib/use-page-title";

export function NoteView() {
  const { id } = useParams<{ id: string }>();
  const note = useNote(id);
  const retry = useRetry(id);
  usePageTitle(
    note.data ? (note.data.status === "in_review" ? "Review draft" : "Voice note") : "Note",
  );
  // The review form remounts on a status change, so the outcome is announced from here.
  const toast = useToast();
  const status = note.data?.status;
  const previous = useRef(status);
  useEffect(() => {
    if (previous.current === "in_review" && status === "confirmed") {
      toast({ title: "Note confirmed", description: "Saved to the patient record and audited." });
    } else if (previous.current === "in_review" && status === "rejected") {
      toast({
        title: "Note rejected",
        description: "Nothing was saved to the patient record.",
        tone: "info",
      });
    }
    previous.current = status;
  }, [status, toast]);

  if (note.isPending) {
    return (
      <SkeletonStatus label="Loading note…">
        <Skeleton className="mb-3 h-3 w-24" />
        <Skeleton className="h-9 w-64" />
        <Skeleton className="mt-3 h-4 w-48" />
        <div className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
          <CardSkeleton lines={4} />
          <div className="flex flex-col gap-6">
            <CardSkeleton lines={2} />
            <CardSkeleton lines={5} />
          </div>
        </div>
      </SkeletonStatus>
    );
  }
  if (note.isError) return <ErrorState error={note.error} />;
  const n = note.data;

  return (
    <>
      <PageHeader
        eyebrow={n.source === "audio" ? "Voice note" : "Typed note"}
        title={n.status === "in_review" ? "Review draft" : "Voice note"}
        subtitle={`${n.source === "audio" ? "Recorded" : "Typed"} ${formatDateTime(n.created_at)}`}
      />
      <div className="mb-6">
        <PipelineStatus note={n} />
      </div>

      {(n.error_step || n.stalled) && (
        <Card className="mb-6 flex flex-wrap items-center gap-4 p-4">
          <div className="flex-1">
            <ErrorState
              error={
                new Error(
                  n.error_step
                    ? (n.error_message ?? "Processing failed.")
                    : "Processing is taking longer than expected. Retry from the last step.",
                )
              }
            />
          </div>
          <Button onClick={() => retry.mutate()} disabled={retry.isPending}>
            {retry.isPending ? "Retrying…" : "Retry"}
          </Button>
        </Card>
      )}

      {isProcessing(n) && (
        <Card
          className="flex flex-col items-center p-12 text-center"
          role="status"
          aria-live="polite"
        >
          <span
            aria-hidden="true"
            className="border-line border-t-brand mb-5 inline-block size-10 animate-spin rounded-full border-[3px] motion-reduce:animate-none"
          />
          <p className="text-ink text-xl font-semibold tracking-[-0.02em]">Processing your note…</p>
          <p className="text-ink-2 mt-2 max-w-md">
            Transcribing, matching the patient, removing personal data and extracting values.
          </p>
        </Card>
      )}

      {n.draft && <DraftReview key={`${n.id}-${n.draft.version}-${n.status}`} note={n} />}
    </>
  );
}

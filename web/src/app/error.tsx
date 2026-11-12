"use client";

import { Button } from "@/shared/ui/button";

export default function Error({ reset }: { error: Error; reset: () => void }) {
  return (
    <main className="mx-auto flex max-w-xl flex-1 flex-col items-start gap-4 px-6 py-24">
      <h1 className="text-4xl font-semibold tracking-[-0.03em]">Something went wrong</h1>
      <p className="text-ink-2">
        The page could not be displayed. No unconfirmed changes were saved to a patient record.
      </p>
      <Button onClick={reset}>Try again</Button>
    </main>
  );
}

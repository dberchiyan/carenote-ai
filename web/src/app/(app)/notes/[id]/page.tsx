import { Suspense } from "react";

import { Loading } from "@/shared/ui/states";

import { NoteView } from "@/features/notes/components/note-view";

export default function NotePage() {
  return (
    <Suspense fallback={<Loading />}>
      <NoteView />
    </Suspense>
  );
}

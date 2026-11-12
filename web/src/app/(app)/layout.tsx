import { Suspense } from "react";

import { AppShell } from "@/features/auth/components/app-shell";
import { Loading } from "@/shared/ui/states";

export default function AppLayout({ children }: LayoutProps<"/">) {
  // The shell reads the URL (active nav item); dynamic routes need a Suspense boundary for that.
  return (
    <Suspense fallback={<Loading />}>
      <AppShell>{children}</AppShell>
    </Suspense>
  );
}

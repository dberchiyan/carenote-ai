"use client";

import { useEffect } from "react";

const APP = "CareNote AI";

/** Browser tab title for a client page: "Ward 3A · CareNote AI". */
export function usePageTitle(title: string | undefined): void {
  useEffect(() => {
    document.title = title ? `${title} · ${APP}` : APP;
  }, [title]);
}

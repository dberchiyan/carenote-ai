"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { homeFor, useMe } from "@/features/auth/hooks";
import { Loading } from "@/shared/ui/states";

/** `/` sends a signed-in user to their role's home and everyone else to the login screen. */
export function HomeRedirect() {
  const me = useMe();
  const router = useRouter();
  useEffect(() => {
    if (me.data) router.replace(homeFor(me.data));
    else if (me.isError) router.replace("/login");
  }, [me.data, me.isError, router]);
  return <Loading />;
}

import { Suspense } from "react";

import { PatientPage } from "@/features/patients/components/patient-page";
import { Loading } from "@/shared/ui/states";

export default function Page() {
  return (
    <Suspense fallback={<Loading />}>
      <PatientPage />
    </Suspense>
  );
}

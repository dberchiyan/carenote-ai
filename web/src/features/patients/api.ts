import { api } from "@/shared/api/client";
import { throwIfNotOk, unwrap } from "@/shared/api/errors";

export const patientsApi = {
  get: async (id: string) =>
    unwrap(await api.GET("/patients/{patient_id}", { params: { path: { patient_id: id } } })),
  observations: async (id: string, days: number) =>
    unwrap(
      await api.GET("/patients/{patient_id}/observations", {
        params: { path: { patient_id: id }, query: { days } },
      }),
    ),
  rules: async () => unwrap(await api.GET("/alerts/rules")),
  /** Download the FHIR bundle as a file (the API also records an audit event). */
  downloadFhir: async (patientId: string, mrn: string): Promise<void> => {
    const response = await fetch(`${window.location.origin}/api/patients/${patientId}/fhir`);
    await throwIfNotOk(response, "Export failed");
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `patient-${mrn}-fhir.json`;
    a.click();
    URL.revokeObjectURL(url);
  },
};

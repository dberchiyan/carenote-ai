import type { Role } from "@/shared/api/types";

/** Something the viewer does that the guide listens for (dispatched with `markGuideStep`). */
export type GuideEvent =
  "note-confirmed" | "fhir-exported" | "audit-change-opened" | "eval-exported";

export type GuideStep = {
  id: string;
  title: string;
  description: string;
  /** Where "Go" takes the viewer. */
  href: string;
  /** Done when the viewer lands on a matching path… */
  route?: RegExp;
  /** …or when the app reports this event. */
  event?: GuideEvent;
};

export type RoleGuide = { intro: string; steps: GuideStep[]; next?: string };

const NOTE_PAGE = /^\/notes\/[0-9a-f-]{36}$/;

export const GUIDES: Record<Role, RoleGuide> = {
  nurse: {
    intro: "You are a ward nurse. Dictate at the bedside, check the AI draft, confirm it.",
    steps: [
      {
        id: "record",
        title: "Record a note",
        description:
          "Speak, upload, or use the sample recording. The transcript appears before you send.",
        href: "/notes/new",
        route: NOTE_PAGE,
      },
      {
        id: "confirm",
        title: "Check and confirm the draft",
        description:
          "Each value is linked to the words it came from. Nothing is saved until you confirm.",
        href: "/notes/new",
        event: "note-confirmed",
      },
      {
        id: "record-view",
        title: "Open the patient record",
        description: "The confirmed values join the trend chart and the observation list.",
        href: "/ward",
        route: /^\/patients\//,
      },
      {
        id: "fhir",
        title: "Export FHIR",
        description: "A standards-based HL7 FHIR R4 bundle, built by code, never by the AI.",
        href: "/ward",
        event: "fhir-exported",
      },
    ],
    next: "Sign in as Carlos Mendes (charge nurse) to see what AI quality and cost look like.",
  },
  charge_nurse: {
    intro: "You run ward 3A. See the whole ward, what the AI costs and how well it does.",
    steps: [
      {
        id: "ward",
        title: "Scan the ward",
        description: "Flags follow the ward's alert rules; drafts waiting for review are counted.",
        href: "/ward",
        route: /^\/ward/,
      },
      {
        id: "metrics",
        title: "See what the AI costs",
        description: "Tokens, cost and latency per day and model, transcription included.",
        href: "/metrics",
        route: /^\/metrics/,
      },
      {
        id: "quality",
        title: "See how well it does",
        description: "Offline evals with every failing case, and what nurses corrected in use.",
        href: "/quality",
        route: /^\/quality/,
      },
      {
        id: "eval-export",
        title: "Turn corrections into tests",
        description:
          "Export nurse corrections as eval cases: today's mistakes, tomorrow's regression tests.",
        href: "/quality",
        event: "eval-exported",
      },
    ],
    next: "Sign in as Aisha Rahman (auditor) to see the audit trail behind every change.",
  },
  auditor: {
    intro: "You review compliance. Every login, edit, confirmation and export is recorded.",
    steps: [
      {
        id: "audit",
        title: "Read the audit log",
        description: "Append-only: the database refuses updates and deletes, even for its owner.",
        href: "/audit",
        route: /^\/audit/,
      },
      {
        id: "change",
        title: "Open a recorded change",
        description: "Before and after, field by field, for every draft edit and confirmation.",
        href: "/audit",
        event: "audit-change-opened",
      },
      {
        id: "metrics",
        title: "Check AI usage",
        description: "Cost and latency for every ward, read-only.",
        href: "/metrics",
        route: /^\/metrics/,
      },
      {
        id: "quality",
        title: "Check AI quality",
        description: "Eval results and nurse corrections across wards.",
        href: "/quality",
        route: /^\/quality/,
      },
    ],
    next: "Sign in as Nora Lindqvist (nurse) to record a note yourself.",
  },
};

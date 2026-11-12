import { readFile } from "node:fs/promises";

import { expect, test } from "./support/fixtures";
import { AccountMenu, AuditPage, LoginPage, NewNotePage, ReviewPage } from "./support/pages";

test("record → review → confirm → export FHIR → audit shows the events", async ({ as }) => {
  // Nurse: upload a recording, confirm the draft.
  const page = await as("nurse");
  const notes = new NewNotePage(page);
  await notes.goto();
  await notes.uploadFixture();
  const review = new ReviewPage(page);
  await review.waitForDraft();
  await review.confirm().click();
  await expect(review.confirmed()).toBeVisible();
  const noteId = review.noteId();

  // Patient page: trend chart, table, FHIR download.
  await review.openPatient().click();
  await expect(page.getByRole("heading", { name: "Keller, Anna" })).toBeVisible();
  await expect(page.getByRole("table")).toContainText("8480-6");
  await expect(page.getByRole("group", { name: /Systolic BP over time/ })).toBeVisible();
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "Export FHIR" }).click(),
  ]);
  const bundle = JSON.parse(await readFile((await download.path()) ?? "", "utf-8")) as {
    resourceType: string;
    type: string;
    entry: { resource: { resourceType: string; code?: { coding: { code: string }[] } } }[];
  };
  expect(bundle.resourceType).toBe("Bundle");
  expect(bundle.type).toBe("transaction");
  expect(bundle.entry[0]?.resource.resourceType).toBe("Patient");
  expect(bundle.entry.some((e) => e.resource.code?.coding[0]?.code === "85354-9")).toBe(true);

  // Auditor: the audit log shows upload, confirm and the export.
  await new AccountMenu(page).signOut();
  await new LoginPage(page).signInAs(/Auditor.*Aisha Rahman/, "Audit log");
  const audit = new AuditPage(page);
  await audit.filterByEntityId(noteId);
  await expect(audit.table()).toContainText("note.upload");
  await expect(audit.table()).toContainText("note.confirm");
  await audit.filterByEntityId("");
  await audit.filterByAction("fhir.export");
  await expect(audit.table()).toContainText("fhir.export");
  await expect(audit.table()).toContainText("Nora Lindqvist");
  // Entity IDs can be copied in full.
  await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);
  await audit
    .table()
    .getByRole("button", { name: /^Copy ID/ })
    .first()
    .click();
  await expect(page.getByRole("status").filter({ hasText: "ID copied" })).toBeVisible();
});

test("charge nurse sees LLM metrics", async ({ as }) => {
  const page = await as("charge");
  await page.getByRole("link", { name: "LLM metrics" }).click();
  await expect(page.getByRole("heading", { name: "LLM metrics" })).toBeVisible();
  await expect(page.getByText("Cost per note")).toBeVisible();
  await expect(page.getByRole("table")).toContainText("rule-based-v1");
});

import { expect, test } from "./support/fixtures";

// Read-only: safe against the public demo (E2E_BASE_URL=https://carenote.osdb.io).
test("the shift handover puts flagged patients first and can be copied", async ({ as }) => {
  const page = await as("charge");
  await page.getByRole("link", { name: "Handover" }).filter({ visible: true }).first().click();
  await expect(page.getByRole("heading", { name: "Ward 3A handover" })).toBeVisible();
  await expect(page.getByRole("list", { name: "Patients by priority" })).toBeVisible();
  const sections = page.getByRole("heading", { level: 2 });
  await expect(sections.first()).toHaveText(/Needs attention|Awaiting review|Stable/);
  await page.getByRole("combobox", { name: "Shift length" }).click();
  await page.getByRole("option", { name: "Last 24 hours" }).click();
  await expect(page).toHaveURL(/hours=24/);
  await expect(page.getByText(/^Last 24 hours ·/)).toBeVisible();
  await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.getByRole("button", { name: "Copy text" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Handover copied" })).toBeVisible();
  const text = await page.evaluate(() => navigator.clipboard.readText());
  expect(text).toMatch(/^Ward 3A handover · last 24 h/);
});

test("auditors do not get a clinical handover", async ({ as }) => {
  const page = await as("auditor");
  await page.goto("/handover");
  await expect(page.getByRole("heading", { name: "No access to this page" })).toBeVisible();
});

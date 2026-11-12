import { expect, test } from "./support/fixtures";

test("charge nurse sees offline evals and exports nurse corrections", async ({ as }) => {
  const page = await as("charge");
  await page.getByRole("link", { name: "AI quality" }).click();
  await expect(page.getByRole("heading", { name: "AI quality", level: 1 })).toBeVisible();

  // The held-out set is shown first; switching to the template set changes the numbers.
  await expect(page.getByRole("button", { name: "Held-out set" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(page.getByText(/Where it fails \(\d+\)/)).toBeVisible();
  await page.getByRole("button", { name: "Template set" }).click();
  await expect(page.getByText("Every case is perfect on this dataset.")).toBeVisible();

  await expect(page.getByRole("heading", { name: "Nurse corrections" })).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "Export as eval cases" }).click();
  expect((await download).suggestedFilename()).toBe("cases_corrections.jsonl");
});

test("nurses do not see the AI quality page", async ({ as }) => {
  const page = await as("nurse");
  await expect(page.getByRole("link", { name: "AI quality" })).toHaveCount(0);
});

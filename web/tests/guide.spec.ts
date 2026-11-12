import { expect, test } from "./support/fixtures";

// Read-only: safe against the public demo too (E2E_BASE_URL=https://carenote.osdb.io).
test("the demo guide lists the role's steps and ticks them as the viewer goes", async ({ as }) => {
  const page = await as("charge");
  const guide = page.getByRole("button", { name: /^Demo guide, \d of 4 steps done$/ });
  await expect(guide).toHaveAccessibleName("Demo guide, 1 of 4 steps done"); // landed on the ward
  await guide.click();
  const panel = page.getByRole("dialog", { name: "Demo guide" });
  await expect(panel).toContainText("Welcome, Carlos");
  await panel.getByRole("link", { name: "Go" }).first().click(); // next step: LLM metrics
  await expect(page.getByRole("heading", { name: "LLM metrics" })).toBeVisible();
  await expect(guide).toHaveAccessibleName("Demo guide, 2 of 4 steps done");
});

test("without a microphone the sample recording gets a transcript before sending", async ({
  as,
}) => {
  test.slow(); // the server transcribes with Whisper
  const page = await as("nurse");
  await page.goto("/notes/new");
  await page.getByRole("button", { name: "No microphone? Use a sample recording" }).click();
  await expect(page.getByText("Microphone: Sample recording (synthetic)")).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Transcript" })).toHaveValue(/Anna Keller/i, {
    timeout: 30_000,
  });
});

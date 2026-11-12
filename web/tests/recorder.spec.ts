import { type Page } from "@playwright/test";

import { expect, signIn, test } from "./support/fixtures";

test.use({
  permissions: ["microphone"],
  launchOptions: {
    args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"],
  },
});

async function recordTwoSeconds(page: Page) {
  await page.goto("/notes/new");
  await page.getByRole("button", { name: "Record", exact: true }).click();
  await expect(page.getByText(/^Microphone: /)).toBeVisible();
  await page.waitForTimeout(2000);
  await page.getByRole("button", { name: "Stop" }).click();
  await expect(page.getByText(/^Recorded /)).toBeVisible();
}

test("a recording from a working microphone plays back with sound", async ({ as }) => {
  const page = await as("nurse");
  await recordTwoSeconds(page);
  await expect(page.getByText("No sound was picked up.")).toHaveCount(0);
  const peak = await page.locator("audio").evaluate(async (audio: HTMLAudioElement) => {
    const data = await (await fetch(audio.src)).arrayBuffer();
    const buffer = await new AudioContext().decodeAudioData(data);
    return Math.max(...buffer.getChannelData(0).map(Math.abs));
  });
  expect(peak).toBeGreaterThan(0.1);
});

test("a silent microphone is reported instead of producing a mute recording", async ({ page }) => {
  // What a browser without OS microphone permission delivers: a live track of zeros.
  await page.addInitScript(() => {
    navigator.mediaDevices.getUserMedia = async () =>
      new AudioContext().createMediaStreamDestination().stream;
  });
  await signIn(page, "nurse");
  await recordTwoSeconds(page);
  await expect(
    page.getByRole("alert").filter({ hasText: "No sound was picked up." }),
  ).toBeVisible();
});

test("a microphone the browser has blocked gets unblocking instructions, not a mute recording", async ({
  page,
}) => {
  // Chrome never asks again once a site is blocked: the nurse has to unblock it herself.
  await page.addInitScript(() => {
    navigator.permissions.query = async () =>
      ({ state: "denied", onchange: null }) as unknown as PermissionStatus;
    navigator.mediaDevices.getUserMedia = async () => {
      throw new DOMException("Permission denied", "NotAllowedError");
    };
  });
  await signIn(page, "nurse");
  await page.goto("/notes/new");
  // Known before the nurse even taps Record.
  const blocked = page.getByRole("alert").filter({ hasText: /blocked/i });
  await expect(blocked).toBeVisible();
  await expect(blocked).toContainText(/address bar/i);
  await page.getByRole("button", { name: "Record", exact: true }).click();
  await expect(page.getByText(/^Recorded /)).toHaveCount(0);
  await expect(page.getByRole("alert").filter({ hasText: /blocked/i })).toBeVisible();
});

test("the nurse can pick which microphone to use", async ({ as }) => {
  const page = await as("nurse");
  await recordTwoSeconds(page);
  const picker = page.getByRole("combobox", { name: "Microphone" });
  await expect(picker).toBeVisible();
  const options = await picker.locator("option").allTextContents();
  expect(options.length).toBeGreaterThan(1);
  await picker.selectOption({ index: 1 });
  await page.getByRole("button", { name: "Record again", exact: true }).click();
  await expect(page.getByText(`Microphone: ${options[1]}`)).toBeVisible();
  await page.getByRole("button", { name: "Stop" }).click();
  await expect(page.getByText(/^Recorded /)).toBeVisible();
});

test("the nurse can type the transcript after recording and the draft is built from it", async ({
  as,
}) => {
  const page = await as("nurse");
  // No on-device recognition under automation: the transcript box is still there to type into,
  // and the server uses it instead of transcribing (which, keyless, would be a sample sentence).
  await recordTwoSeconds(page);
  // The server transcribes the take first (Whisper, a few seconds under load); the box is
  // editable once that is done, whatever it heard in a test tone.
  await expect(page.getByText("Transcribing on the server…")).toHaveCount(0, { timeout: 30_000 });
  const box = page.getByRole("textbox", { name: "Transcript" });
  await box.fill("John, 80 pulse, headache");
  await page.getByRole("button", { name: "Use this recording and transcript" }).click();
  await expect(page.getByRole("heading", { name: "Review draft" })).toBeVisible({ timeout: 30000 });
  await expect(page.getByText("John, 80 pulse, headache")).toBeVisible();
  await expect(page.getByText("Sample transcript.")).toHaveCount(0);
  await expect(page.getByText("Smith, John")).toBeVisible();
  await expect(page.getByRole("combobox").filter({ hasText: "Heart rate" }).first()).toBeVisible();
});

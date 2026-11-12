import { expect, test } from "./support/fixtures";
import { AccountMenu, LoginPage, WardPage } from "./support/pages";

test("login page shows the synthetic-data notice and a healthy API", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "CareNote AI" })).toBeVisible();
  await expect(page.getByText(/synthetic data only/i).first()).toBeVisible();
  await expect(page.getByText("Operational")).toBeVisible();
});

test("nurse signs in and sees only their ward", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /Nurse.*Nora Lindqvist/ }).click();
  await expect(page.getByRole("heading", { name: "Ward 3A" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Keller, Anna", exact: true })).toBeVisible();
  await expect(page.getByText("Braun, Peter")).toHaveCount(0);
});

test("the desktop menu collapses to icons and remembers it", async ({ page, isMobile }) => {
  test.skip(isMobile || (page.viewportSize()?.width ?? 0) < 1024, "sidebar is desktop-only");
  await page.goto("/login");
  await page.getByRole("button", { name: /Nurse.*Nora Lindqvist/ }).click();
  await expect(page.getByRole("heading", { name: "Ward 3A" })).toBeVisible();

  await page.getByRole("button", { name: "Collapse menu" }).click();
  const expand = page.getByRole("button", { name: "Expand menu" });
  await expect(expand).toHaveAttribute("aria-expanded", "false");
  // Labels are visually hidden, but links keep their accessible names.
  await expect(page.getByRole("link", { name: "Record note" }).first()).toBeVisible();

  await page.reload();
  await expect(expand).toBeVisible();
  await expand.click();
  await expect(page.getByRole("button", { name: "Collapse menu" })).toBeVisible();
});

test("a page outside the role says so instead of loading forever", async ({ as }) => {
  const page = await as("nurse");
  await page.goto("/quality");
  await expect(page.getByRole("heading", { name: "No access to this page" })).toBeVisible();
  await expect(page.getByText(/charge nurse.*auditor/i)).toBeVisible();
  await expect(page.getByRole("status")).toHaveCount(0);
  await page.getByRole("link", { name: "Back to your home page" }).click();
  await expect(page.getByRole("heading", { name: "Ward 3A" })).toBeVisible();

  await new AccountMenu(page).signOut();
  await new LoginPage(page).signInAs(/Auditor.*Aisha Rahman/, "Audit log");
  for (const path of ["/notes/new", "/ward"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { name: "No access to this page" })).toBeVisible();
  }
});

test("on a phone the ward is a card list under a tab bar, with nothing to scroll sideways", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/login");
  await page.getByRole("button", { name: /Nurse.*Nora Lindqvist/ }).click();
  await expect(page.getByRole("heading", { name: "Ward 3A" })).toBeVisible();
  // The table is for wide screens; phones get one tappable card per patient.
  await expect(page.getByRole("table")).toHaveCount(0);
  const card = page
    .getByRole("list", { name: "Patients" })
    .getByRole("link", { name: /Keller, Anna/ });
  await expect(card).toBeVisible();
  expect((await card.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(44);
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBe(0);
  // Navigation moved to the bottom, within thumb reach.
  const tabs = page.getByRole("navigation", { name: "Main" }).filter({ visible: true });
  await expect(tabs.getByRole("link", { name: "Record note" })).toBeVisible();
  const box = await tabs.boundingBox();
  expect((box?.y ?? 0) + (box?.height ?? 0)).toBeGreaterThan(800);
});

test("the theme toggle switches to dark, survives a reload and goes back to system", async ({
  page,
}) => {
  await page.goto("/login");
  const html = page.locator("html");
  await page.getByRole("button", { name: "Dark theme" }).click();
  await expect(html).toHaveAttribute("data-theme", "dark");
  await expect(page.getByRole("button", { name: "Dark theme" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await page.reload();
  await expect(html).toHaveAttribute("data-theme", "dark");
  // Dark tokens are in effect: the page canvas is no longer light.
  const bg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  expect(bg).not.toBe("rgb(243, 245, 247)");
  await page.getByRole("button", { name: "System theme" }).click();
  await expect(html).not.toHaveAttribute("data-theme", /./);
});

test("patients can be searched and narrowed to flagged ones, with the filter in the URL", async ({
  as,
}) => {
  const page = await as("nurse");
  const ward = new WardPage(page);
  await expect(page).toHaveTitle("Ward 3A · CareNote AI");
  await expect(ward.patient("Keller, Anna")).toBeVisible();
  const before = await ward.rows().count();
  expect(before).toBeGreaterThan(3);

  await ward.search().fill("keller");
  await expect(ward.rows()).toHaveCount(3); // header + Anna + Hanna
  await expect(page).toHaveURL(/\?q=keller$/);
  await ward.search().fill("zzz");
  await expect(page.getByText("No patients match.")).toBeVisible();
  await ward.search().fill("");
  await expect(ward.rows()).toHaveCount(before);

  await ward.flaggedOnly().click();
  await expect(ward.flaggedOnly()).toHaveAttribute("aria-pressed", "true");
  const flagged = await ward.rows().count();
  expect(flagged).toBeLessThan(before);
  await expect(page.getByRole("table").getByText("Normal", { exact: true })).toHaveCount(0);
  // The filtered view survives a reload: it is the URL.
  await page.reload();
  await expect(ward.flaggedOnly()).toHaveAttribute("aria-pressed", "true");
  await expect(ward.rows()).toHaveCount(flagged);
});

test("the account menu shows who is signed in, switches the theme and signs out", async ({
  as,
}) => {
  const page = await as("nurse");
  const trigger = page.getByRole("button", { name: /^Account: Nora Lindqvist/ });
  await expect(trigger).toHaveAttribute("aria-expanded", "false");
  await trigger.click();
  const menu = page.getByRole("dialog", { name: "Account" });
  await expect(menu).toContainText("Nurse · Ward 3A");
  await menu.getByRole("button", { name: "Dark theme" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.keyboard.press("Escape");
  await expect(menu).toHaveCount(0);
  await expect(trigger).toBeFocused();
  await trigger.click();
  await menu.getByRole("button", { name: "System theme" }).click();
  await menu.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login$/);
});

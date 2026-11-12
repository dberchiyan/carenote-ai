import path from "node:path";

import { expect, type Page } from "@playwright/test";

export const AUDIO_FIXTURE = path.join(__dirname, "..", "fixtures", "note.wav");

/** Page objects: the locators the specs share, named after what the nurse sees. */
export class LoginPage {
  constructor(readonly page: Page) {}
  async goto() {
    await this.page.goto("/login");
  }
  user(pattern: RegExp) {
    return this.page.getByRole("button", { name: pattern });
  }
  async signInAs(pattern: RegExp, landing: string) {
    await this.goto();
    await this.user(pattern).click();
    await expect(this.page.getByRole("heading", { name: landing })).toBeVisible();
  }
}

export class WardPage {
  constructor(readonly page: Page) {}
  readonly heading = () => this.page.getByRole("heading", { name: /^Ward / });
  readonly search = () => this.page.getByRole("searchbox", { name: "Search patients" });
  readonly flaggedOnly = () => this.page.getByRole("button", { name: "Flagged only" });
  readonly rows = () => this.page.getByRole("table").getByRole("row");
  patient(name: string) {
    return this.page.getByRole("link", { name, exact: true });
  }
}

export class NewNotePage {
  constructor(readonly page: Page) {}
  async goto() {
    await this.page.goto("/notes/new");
  }
  async typeNote(text: string) {
    await this.page.getByRole("tab", { name: "Type" }).click();
    await this.page.getByLabel("Note text").fill(text);
    await this.page.getByRole("button", { name: "Create draft" }).click();
  }
  async uploadFixture() {
    await this.page.getByRole("tab", { name: "Upload file" }).click();
    await this.page.getByLabel(/Audio file/).setInputFiles(AUDIO_FIXTURE);
    await this.page.getByRole("button", { name: "Upload and process" }).click();
  }
}

export class ReviewPage {
  constructor(readonly page: Page) {}
  readonly heading = () => this.page.getByRole("heading", { name: "Review draft" });
  readonly confirm = () => this.page.getByRole("button", { name: "Confirm" });
  readonly confirmed = () => this.page.getByText(/^✓ Confirmed/);
  readonly openPatient = () => this.page.getByRole("link", { name: "Open patient record" });
  candidate(name: RegExp) {
    return this.page.getByRole("radio", { name });
  }
  vital(label: string) {
    return this.page.getByLabel(`${label} value`);
  }
  async waitForDraft() {
    await expect(this.heading()).toBeVisible({ timeout: 30_000 });
  }
  noteId() {
    return this.page.url().split("/").at(-1) ?? "";
  }
}

export class AuditPage {
  constructor(readonly page: Page) {}
  readonly table = () => this.page.getByRole("table");
  async filterByEntityId(id: string) {
    await this.page.getByLabel("Entity ID").fill(id);
  }
  async filterByAction(action: string) {
    await this.page.getByLabel("Action").selectOption(action);
  }
}

export class AccountMenu {
  constructor(readonly page: Page) {}
  readonly trigger = () => this.page.getByRole("button", { name: /^Account:/ });
  readonly dialog = () => this.page.getByRole("dialog", { name: "Account" });
  async signOut() {
    await this.trigger().click();
    await this.dialog().getByRole("button", { name: "Sign out" }).click();
    await expect(this.page).toHaveURL(/\/login$/);
  }
}

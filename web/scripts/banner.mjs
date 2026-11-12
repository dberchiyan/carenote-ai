/**
 * Renders docs/banner.png from the running stack: three real screens (phone recorder, the review
 * of a self-corrected dictation, the AI quality page in dark mode) composed on a dark canvas.
 *
 *   make banner        # stack up and seeded; writes docs/banner.png (2400x1200)
 */
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

import { chromium, request } from "playwright";

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:3000";
const OUT = path.resolve(process.argv[2] ?? "../docs/banner.png");
const DICTATION =
  "Mrs. Clara Klein, blood pressure 129 over 82, pulse 89, sorry, I mean 83, " +
  "sats 96 percent, respiratory rate 13.";

async function signedIn(browser, role, options = {}) {
  const api = await request.newContext({ baseURL: BASE });
  const login = await api.post("/api/auth/demo-login", { data: { username: role } });
  if (!login.ok()) throw new Error(`login as ${role}: ${login.status()}`);
  const context = await browser.newContext({
    baseURL: BASE,
    storageState: await api.storageState(),
    deviceScaleFactor: 2,
    ...options,
  });
  await api.dispose();
  return context;
}

async function reviewNote(context) {
  const page = await context.newPage();
  const created = await page.request.post("/api/notes/text", { data: { text: DICTATION } });
  const note = await created.json();
  for (let i = 0; i < 40; i++) {
    const current = await (await page.request.get(`/api/notes/${note.id}`)).json();
    if (current.status === "in_review") return { page, id: note.id };
    await page.waitForTimeout(500);
  }
  throw new Error("the banner note never reached review");
}

const browser = await chromium.launch();
const dir = await mkdtemp(path.join(tmpdir(), "carenote-banner-"));
const shots = {};

// 1. Phone: the recorder, light.
{
  const context = await signedIn(browser, "nurse", { viewport: { width: 390, height: 760 } });
  const page = await context.newPage();
  await page.goto(`${BASE}/notes/new`);
  await page.getByRole("button", { name: "Record", exact: true }).waitFor();
  await page.waitForTimeout(400);
  shots.phone = path.join(dir, "phone.png");
  await page.screenshot({ path: shots.phone });
  await context.close();
}

// 2. Desktop: the review of a dictation with a spoken correction, light.
let noteId;
{
  const context = await signedIn(browser, "nurse", { viewport: { width: 1280, height: 880 } });
  const { page, id } = await reviewNote(context);
  noteId = id;
  await page.goto(`${BASE}/notes/${id}`);
  await page.getByRole("heading", { name: "Review draft" }).waitFor();
  await page.getByText("Corrected while dictating").first().waitFor();
  await page.getByRole("button", { name: "Collapse menu" }).click();
  await page.waitForTimeout(500);
  shots.review = path.join(dir, "review.png");
  await page.screenshot({ path: shots.review });
  await page.request.post(`/api/notes/${id}/reject`, { data: { reason: "banner screenshot" } });
  await context.close();
}

// 3. Desktop: AI quality, dark.
{
  const context = await signedIn(browser, "charge", {
    viewport: { width: 1280, height: 880 },
    colorScheme: "dark",
  });
  await context.addInitScript(() => localStorage.setItem("carenote.theme", "dark"));
  const page = await context.newPage();
  await page.goto(`${BASE}/quality`);
  await page.getByText(/Where it fails/).waitFor();
  await page.waitForTimeout(500);
  shots.quality = path.join(dir, "quality.png");
  await page.screenshot({ path: shots.quality });
  await context.close();
}

// 4. Compose.
const data = async (file) => `data:image/png;base64,${(await readFile(file)).toString("base64")}`;
const html = `<!doctype html><html><head><meta charset="utf-8"><style>
  * { margin: 0; box-sizing: border-box; }
  body { width: 2400px; height: 1200px; overflow: hidden; position: relative;
    background: radial-gradient(ellipse at 20% 0%, #0f2f2c 0%, #0a1724 55%, #070e17 100%); }
  .grid { position: absolute; inset: 0; opacity: .08;
    background-image: linear-gradient(#5eead4 1px, transparent 1px), linear-gradient(90deg, #5eead4 1px, transparent 1px);
    background-size: 60px 60px; mask-image: radial-gradient(ellipse at 30% 20%, #000 20%, transparent 75%); }
  .glow { position: absolute; width: 900px; height: 900px; border-radius: 50%; filter: blur(140px); opacity: .35;
    background: #0b6e69; left: -200px; top: -300px; }
  .shot { position: absolute; overflow: hidden; background: #fff;
    box-shadow: 0 40px 120px rgba(0,0,0,.6), 0 0 0 1px rgba(255,255,255,.08); }
  .shot img { display: block; width: 100%; }
  .quality { left: 1110px; top: 95px; width: 1230px; border-radius: 22px; opacity: .92; filter: brightness(.92); }
  .review { left: 585px; top: 225px; width: 1290px; border-radius: 22px; }
  .phone { left: 150px; top: 190px; width: 400px; border-radius: 44px; border: 10px solid #0b1a2a;
    box-shadow: 0 40px 100px rgba(0,0,0,.65), 0 0 0 2px rgba(255,255,255,.12); }
  .fade { position: absolute; left: 0; right: 0; bottom: 0; height: 220px;
    background: linear-gradient(transparent, #070e17); }
</style></head><body>
  <div class="glow"></div><div class="grid"></div>
  <div class="shot quality"><img src="${await data(shots.quality)}"></div>
  <div class="shot review"><img src="${await data(shots.review)}"></div>
  <div class="shot phone"><img src="${await data(shots.phone)}"></div>
  <div class="fade"></div>
</body></html>`;
const compose = path.join(dir, "banner.html");
await writeFile(compose, html);
const page = await browser.newPage({
  viewport: { width: 2400, height: 1200 },
  deviceScaleFactor: 1,
});
await page.goto(`file://${compose}`);
await page.waitForTimeout(300);
await page.screenshot({ path: OUT, type: "png" });
await browser.close();
await rm(dir, { recursive: true, force: true });
console.log(`wrote ${OUT}${noteId ? ` (banner note ${noteId} rejected)` : ""}`);

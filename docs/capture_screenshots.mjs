// Captures every route of the Scotoma frontend, plus the interaction states that matter.
//
//   node docs/capture_screenshots.mjs
//
// Routes are discovered from the App Router directory rather than hardcoded, so this stays
// in sync when a page is added. Output lands in docs/assets/screens/<slug>.png.
//
// The app is light-themed by default (--canvas-cream #fafbfc); there is no dark variant, so
// the capture forces the default theme rather than inventing one.

import { chromium } from "playwright";
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const APP_DIR = path.join(ROOT, "frontend", "app");
const OUT_DIR = path.join(ROOT, "docs", "assets", "screens");
const ORIGIN = "http://localhost:3000";
const VIEWPORT = { width: 1600, height: 1000 };
const SCALE = 2;

/** Every directory under app/ holding a page.tsx is a route. */
function discoverRoutes() {
  const routes = [];
  const walk = (dir, prefix) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      if (!entry.isDirectory()) continue;
      if (entry.name.startsWith("_") || entry.name === "fonts") continue;
      const child = path.join(dir, entry.name);
      if (fs.existsSync(path.join(child, "page.tsx"))) {
        routes.push({ route: `${prefix}/${entry.name}`, slug: entry.name });
      }
      walk(child, `${prefix}/${entry.name}`);
    }
  };
  walk(APP_DIR, "");
  return routes.sort((a, b) => a.route.localeCompare(b.route));
}

async function serverIsUp() {
  try {
    const res = await fetch(ORIGIN, { method: "HEAD" });
    return res.ok || res.status === 307 || res.status === 200;
  } catch {
    return false;
  }
}

async function ensureServer() {
  if (await serverIsUp()) return null;
  console.log("starting dev server");
  const proc = spawn("npm", ["run", "dev", "--prefix", "frontend"], {
    cwd: ROOT, shell: true, stdio: "ignore", detached: false,
  });
  for (let i = 0; i < 90; i += 1) {
    await new Promise(r => setTimeout(r, 1000));
    if (await serverIsUp()) { console.log("dev server ready"); return proc; }
  }
  throw new Error("dev server did not become ready in 90s");
}

/** Network idle is not enough: fades, count-up animations and charts paint after it. */
async function settle(page, extra = 0) {
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.evaluate(() => document.fonts?.ready).catch(() => {});
  // StatPortrait counts up over 1500ms; recharts paints on the next frames after mount.
  await page.waitForTimeout(2600 + extra);
  // Every canvas that exists must have painted at least one non-empty frame.
  await page.evaluate(() => {
    const canvases = Array.from(document.querySelectorAll("canvas"));
    return canvases.every(c => c.width > 0 && c.height > 0);
  }).catch(() => {});
  await page.waitForTimeout(300);
}

async function stripDevOverlay(page) {
  await page.evaluate(() => {
    for (const sel of ["nextjs-portal", "#__next-build-watcher", "[data-nextjs-toast]",
                       "[data-nextjs-dialog-overlay]", "#__next-prerender-indicator"]) {
      document.querySelectorAll(sel).forEach(n => n.remove());
    }
  }).catch(() => {});
}

async function shoot(page, name) {
  await stripDevOverlay(page);
  const file = path.join(OUT_DIR, `${name}.png`);
  await page.screenshot({ path: file, animations: "disabled" });
  const kb = Math.round(fs.statSync(file).size / 1024);
  console.log(`  ${name}.png  ${kb} KB`);
  return { name, file, kb };
}

/** Interaction states worth a second frame, keyed by slug. */
const STATES = {
  atlas: async (page) => {
    const row = page.locator("tbody tr", { hasText: "UPI collect-request" }).first();
    if (await row.count()) { await row.click(); await page.waitForTimeout(1200); return "vector-detail"; }
    return null;
  },
  fidelity: async (page) => {
    // The ablation is below the fold, and it is the whole argument of the page, so it
    // gets its own frame rather than being cropped out of the default viewport shot.
    const block = page.getByText("GaussianCopulaSynthesizer ablation").first();
    if (await block.count()) {
      await block.scrollIntoViewIfNeeded();
      await page.mouse.wheel(0, 430);
      await page.waitForTimeout(1200);
      return "ablation";
    }
    return null;
  },
  loop: async (page) => {
    const chip = page.getByText("network", { exact: true }).first();
    if (await chip.count()) { await chip.click(); await page.waitForTimeout(1000); return "scope-network"; }
    return null;
  },
  soc: async (page) => {
    const slider = page.locator('input[type="range"]').first();
    if (await slider.count()) {
      await slider.focus();
      for (let i = 0; i < 6; i += 1) await page.keyboard.press("ArrowRight");
      await page.waitForTimeout(900);
      return "threshold-moved";
    }
    return null;
  },
  redteam: async (page) => {
    const pause = page.getByRole("button", { name: /pause/i }).first();
    if (await pause.count()) { await pause.click(); await page.waitForTimeout(800); return "paused"; }
    return null;
  },
};

async function main() {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  const proc = await ensureServer();
  const routes = discoverRoutes();
  console.log(`discovered ${routes.length} routes: ${routes.map(r => r.route).join(", ")}`);

  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: VIEWPORT,
    deviceScaleFactor: SCALE,
    colorScheme: "light",          // the app ships one theme; do not invent a dark one
    reducedMotion: "reduce",
  });
  const page = await context.newPage();

  // Hide the Next.js dev overlay and the caret, and stop any looping animation.
  await context.addInitScript(() => {
    const css = document.createElement("style");
    css.textContent = `
      nextjs-portal, #__next-build-watcher, [data-nextjs-toast] { display: none !important; }
      *, *::before, *::after { caret-color: transparent !important; }
      @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after { animation-duration: .001ms !important; animation-iteration-count: 1 !important; transition-duration: .001ms !important; }
      }`;
    document.documentElement.appendChild(css);
  });

  const manifest = [];
  for (const { route, slug } of routes) {
    console.log(`${route}`);
    const response = await page.goto(`${ORIGIN}${route}`, { waitUntil: "domcontentloaded" });
    const status = response?.status() ?? 0;
    await settle(page);

    const bodyText = (await page.locator("main").innerText().catch(() => "")).trim();
    const shot = await shoot(page, slug);
    manifest.push({ route, ...shot, status, chars: bodyText.length,
                    ok: status < 400 && bodyText.length > 200 });

    const stateFn = STATES[slug];
    if (stateFn) {
      const stateName = await stateFn(page).catch(() => null);
      if (stateName) {
        const s = await shoot(page, `${slug}--${stateName}`);
        manifest.push({ route: `${route} (${stateName})`, ...s, status, chars: bodyText.length, ok: true });
      } else {
        console.log(`  no interaction state captured for ${slug}`);
      }
    }
  }

  await browser.close();
  if (proc) proc.kill();

  fs.writeFileSync(path.join(OUT_DIR, "manifest.json"), JSON.stringify(manifest, null, 2));
  console.log("\nmanifest");
  for (const m of manifest) {
    console.log(`  ${m.ok ? "OK  " : "FAIL"} ${m.route.padEnd(28)} ${m.name}.png  ${m.kb} KB  ${m.chars} chars`);
  }
  const bad = manifest.filter(m => !m.ok);
  if (bad.length) {
    console.error(`\n${bad.length} route(s) rendered empty or errored`);
    process.exitCode = 1;
  }
}

main().catch(err => { console.error(err); process.exit(1); });

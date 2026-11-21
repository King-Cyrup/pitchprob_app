export default async function run(page, ui) {
  const errs = [];
  page.on("console", (m) => errs.push(m.type() + ": " + m.text()));
  page.on("pageerror", (e) => errs.push("PAGEERROR: " + e.message + " | " + (e.stack || "").split("\n").slice(0, 4).join(" // ")));
  await page.goto("http://127.0.0.1:3000/?date=2026-11-24", { waitUntil: "domcontentloaded" });
  await page.waitForSelector("[class*='matchRow']", { timeout: 20000 });
  await page.waitForTimeout(4000);

  const before = await page.evaluate(() => ({
    theme: document.documentElement.dataset.theme ?? null,
    bodyChildKeys: Object.keys(document.body).filter((k) => k.startsWith("__react")),
    hasNextRoot: !!document.querySelector("[data-reactroot]"),
    nextF: typeof self.__next_f,
    nextRouter: typeof window.next,
    btnKeys: (() => { const b = document.querySelector("[class*='rowButton']"); return b ? Object.keys(b) : null; })(),
  }));

  // click theme toggle (pure client component)
  await page.evaluate(() => {
    const btn = [...document.querySelectorAll("button")].find((b) => (b.getAttribute("aria-label") || "").startsWith("Switch to"));
    btn?.click();
  });
  await page.waitForTimeout(800);
  const afterTheme = await page.evaluate(() => document.documentElement.dataset.theme ?? null);

  // click collapse sidebar (pure client component in AppShell)
  await page.evaluate(() => {
    const btn = [...document.querySelectorAll("button")].find((b) => (b.getAttribute("aria-label") || "").includes("sidebar"));
    btn?.click();
  });
  await page.waitForTimeout(800);
  const afterCollapse = await page.evaluate(() => document.querySelector("aside")?.className);

  return { before, afterTheme, afterCollapse, errs: errs.slice(0, 30) };
}

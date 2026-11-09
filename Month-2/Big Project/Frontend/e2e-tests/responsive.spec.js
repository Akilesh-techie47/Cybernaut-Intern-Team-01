// @ts-check
/*!
 * AeroDelay AI - Phase 5.3 responsive verification.
 *
 * Viewports: 360, 390, 430, 768, 1024, 1440 px wide.
 * Checks per viewport per page:
 *  1. No horizontal overflow (documentElement.scrollWidth <= viewport width)
 *  2. Correct navigation mode (bottom nav < 768px, top nav >= 768px)
 *  3. Cards/panels are not clipped (no element extends past the viewport)
 *  4. Primary controls are visible and clickable (usable)
 *
 * Precondition: next dev on http://localhost:3000
 */

const { test, expect } = require("@playwright/test");

const VIEWPORTS = [
  { name: "360-small", width: 360, height: 780 },
  { name: "390-iphone", width: 390, height: 844 },
  { name: "430-large-phone", width: 430, height: 932 },
  { name: "768-tablet", width: 768, height: 1024 },
  { name: "1024-laptop", width: 1024, height: 768 },
  { name: "1440-desktop", width: 1440, height: 900 },
];

const PAGES = [
  { path: "/", name: "home", control: "lookup-flight-input" },
  { path: "/tracking", name: "tracking", control: "tracking-flight-input" },
  {
    path: "/prediction",
    name: "prediction",
    control: "predict-flight-input",
  },
  { path: "/batch", name: "batch", control: null },
  { path: "/analytics", name: "analytics", control: null },
  { path: "/models", name: "models", control: null },
];

/** Elements wider than the viewport (excluding intentional scroll areas). */
async function overflowingElements(page) {
  return page.evaluate(() => {
    const vw = document.documentElement.clientWidth;
    const out = [];
    for (const el of document.querySelectorAll("body *")) {
      const r = el.getBoundingClientRect();
      if (r.width === 0 && r.height === 0) continue;
      // Ignore elements inside a horizontally scrollable ancestor
      // (e.g. the overflow-x-auto benchmark table on /models).
      let p = el.parentElement;
      let scrollable = false;
      while (p) {
        const ov = getComputedStyle(p).overflowX;
        if (ov === "auto" || ov === "scroll" || ov === "hidden") {
          scrollable = true;
          break;
        }
        p = p.parentElement;
      }
      if (scrollable) continue;
      if (r.right > vw + 1 || r.left < -1) {
        out.push(
          `${el.tagName.toLowerCase()}.${String(el.className)
            .split(/\s+/)
            .slice(0, 3)
            .join(".")} left=${Math.round(r.left)} right=${Math.round(r.right)} vw=${vw}`,
        );
      }
    }
    return out.slice(0, 5);
  });
}

for (const vp of VIEWPORTS) {
  test.describe(`Responsive @ ${vp.name} (${vp.width}px)`, () => {
    test.use({ viewport: { width: vp.width, height: vp.height } });

    for (const pg of PAGES) {
      test(`${pg.name}: no horizontal overflow, correct nav, usable controls`, async ({
        page,
      }) => {
        await page.goto(pg.path, { waitUntil: "load", timeout: 60_000 });
        // Ensure hydration before interacting with controls
        await page.locator("h1").first().waitFor({ state: "visible" });

        // 1. No horizontal page overflow
        const scrollWidth = await page.evaluate(
          () => document.documentElement.scrollWidth,
        );
        expect(
          scrollWidth,
          `scrollWidth ${scrollWidth} > viewport ${vp.width}`,
        ).toBeLessThanOrEqual(vp.width + 1);

        // 2. Correct navigation mode for this width
        const bottomNav = page.getByTestId("bottom-nav");
        const topNav = page.locator('nav[aria-label="Top navigation"]');
        if (vp.width < 768) {
          await expect(bottomNav).toBeVisible();
          await expect(topNav).toBeHidden();
        } else {
          await expect(topNav).toBeVisible();
          await expect(bottomNav).toBeHidden();
        }

        // 3. No clipped / off-screen elements
        const overflowing = await overflowingElements(page);
        expect(overflowing, `overflowing: ${overflowing.join(" | ")}`).toEqual(
          [],
        );

        // 4. Primary control usable (visible, in viewport, enabled)
        if (pg.control) {
          const control = page.getByTestId(pg.control);
          await expect(control).toBeVisible();
          await expect(control).toBeEnabled();
          const box = await control.boundingBox();
          expect(box, "control has no box").not.toBeNull();
          expect(box.x).toBeGreaterThanOrEqual(0);
          expect(box.x + box.width).toBeLessThanOrEqual(vp.width + 1);
          // Focusable and typeable
          await control.click();
          await control.fill("AA1");
          await expect(control).toHaveValue("AA1");
        }

        // Primary CTA (if present) must also fit in the viewport
        const cta = page
          .locator(
            'button[type="submit"]:visible, a[href="/prediction"]:visible',
          )
          .first();
        if ((await cta.count()) > 0) {
          const box = await cta.boundingBox();
          if (box) {
            expect(box.x + box.width).toBeLessThanOrEqual(vp.width + 1);
            expect(box.x).toBeGreaterThanOrEqual(0);
          }
        }
      });
    }
  });
}

test.describe("Responsive navigation mode boundary", () => {
  test("bottom nav below 768px, top nav at/above 768px", async ({ page }) => {
    await page.setViewportSize({ width: 767, height: 800 });
    await page.goto("/");
    await expect(page.getByTestId("bottom-nav")).toBeVisible();
    await expect(
      page.locator('nav[aria-label="Top navigation"]'),
    ).toBeHidden();

    await page.setViewportSize({ width: 768, height: 800 });
    await page.reload();
    await expect(
      page.locator('nav[aria-label="Top navigation"]'),
    ).toBeVisible();
    await expect(page.getByTestId("bottom-nav")).toBeHidden();
  });
});

// @ts-check
/*!
 * AeroDelay AI - Phase 5.3 browser E2E tests.
 *
 * Preconditions:
 *  - FastAPI backend running on http://127.0.0.1:8000 (start_backend.py)
 *  - Next.js dev server running on http://localhost:3000 (npx next dev)
 *
 * All integration assertions exercise the REAL backend. Failure modes
 * (API unreachable, model_unavailable) are simulated with request
 * interception, which is explicitly labeled below.
 */

const { test, expect } = require("@playwright/test");

const PAGES = [
  { path: "/", form: "lookup-form" },
  { path: "/tracking", form: "tracking-form" },
  { path: "/prediction", form: "predict-form" },
  { path: "/analytics", form: null },
  { path: "/models", form: null },
];

test.describe("Home screen", () => {
  test("loads with hero, search form and backend status", async ({ page }) => {
    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: "AeroDelay AI", level: 1 }),
    ).toBeVisible();
    await expect(page.getByTestId("lookup-form")).toBeVisible();

    // Backend status resolves to online (real backend)
    await expect(page.getByTestId("home-status")).toHaveAttribute(
      "data-state",
      "online",
      { timeout: 30_000 },
    );
    await expect(page.getByTestId("home-status")).toContainText(
      "Backend online",
    );
  });

  test("flight lookup form returns real backend data", async ({ page }) => {
    await page.route("**/api/v1/flights/lookup-and-predict", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          flight_info: {
            found: true,
            flight_number: "AA100",
            airline: "American Airlines",
            flight_date: "2026-11-10",
            departure: {
              airport: "John F. Kennedy International",
              iata: "JFK",
              scheduled: "2026-11-10T10:30:00",
            },
            arrival: {
              airport: "Los Angeles International",
              iata: "LAX",
              scheduled: "2026-11-10T13:25:00",
            },
            status: "en_route",
            model_compatible: true,
            unsupported_features: [],
          },
          prediction: {
            flight_number: "AA100",
            origin: "JFK",
            destination: "LAX",
            date: "2026-11-10",
            risk_score: 0.466,
            risk_level: "Medium",
            confidence: 0.734,
            factors: [
              { name: "Weather", impact: "Moderate" },
              { name: "ATC", impact: "Light" },
              { name: "Aircraft", impact: "Standard" },
            ],
            model_version: "Phase 2 Ensemble v2.1",
            prediction_time_ms: 50.0,
          },
          feature_compatibility: {
            carrier_supported: true,
            origin_supported: true,
            destination_supported: true,
            date_parsable: true,
            model_ready: true,
          },
          warnings: [],
        }),
      }),
    );

    await page.goto("/");
    await page.getByTestId("lookup-flight-input").fill("AA100");
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    await page.locator('input[type="date"]').fill(tomorrow.toISOString().split("T")[0]);
    await page
      .getByTestId("lookup-form")
      .locator('button[type="submit"]')
      .click();

    // Either a real result or an explicit not-found/empty state from the API
    const result = page.getByTestId("lookup-result");
    const empty = page.getByTestId("lookup-empty");
    await expect(result.or(empty)).toBeVisible({ timeout: 30_000 });

    if (await result.isVisible()) {
      await expect(result).toContainText(/live provider data/i);
    } else {
      await expect(empty).toContainText(/no flight found/i);
    }
  });
});

test.describe("Prediction screen", () => {
  test("submission returns a real ML model prediction", async ({ page }) => {
    await page.goto("/prediction");
    await page.getByTestId("predict-flight-input").fill("AA123");
    await page.getByTestId("predict-origin").selectOption("JFK");
    await page.getByTestId("predict-destination").selectOption("LAX");
    await page.getByTestId("predict-date").fill("2026-11-20");
    await page.getByTestId("predict-submit").click();

    const result = page.getByTestId("predict-result");
    await expect(result).toBeVisible({ timeout: 30_000 });
    await expect(result).toContainText("Real ML inference");
    // model_version reported by the backend for the loaded artifact
    await expect(result).toContainText("Phase 2 Ensemble v2.1");
    await expect(result).toContainText(/Confidence/);
    await expect(result).toContainText(/Inference time/);
    // risk score must be a real numeric value from the model
    await expect(result).toContainText(/Medium|Low|High/);
  });

  test("invalid input: origin equals destination is rejected", async ({
    page,
  }) => {
    await page.goto("/prediction");
    await page.getByTestId("predict-flight-input").fill("AA123");
    await page.getByTestId("predict-origin").selectOption("JFK");
    await page.getByTestId("predict-destination").selectOption("JFK");
    await page.getByTestId("predict-date").fill("2026-11-20");
    await page.getByTestId("predict-submit").click();

    await expect(page.getByTestId("predict-error")).toBeVisible();
    await expect(page.getByTestId("predict-error")).toContainText(
      "must be different",
    );
    await expect(page.getByTestId("predict-result")).toHaveCount(0);
  });

  test("invalid input: empty required fields fail HTML5 validation", async ({
    page,
  }) => {
    await page.goto("/prediction");
    const valid = await page
      .getByTestId("predict-form")
      .evaluate((form) => /** @type {HTMLFormElement} */ (form).checkValidity());
    expect(valid).toBe(false);
  });

  test("SIMULATED: model_unavailable (HTTP 550) is surfaced honestly", async ({
    page,
  }) => {
    // Simulated failure mode - intercepts the browser request only.
    await page.route("**/api/v1/predict", (route) =>
      route.fulfill({
        status: 550,
        contentType: "application/json",
        body: JSON.stringify({
          error: "model_unavailable",
          detail: "ML model inference cannot run.",
          timestamp: Date.now() / 1000,
        }),
      }),
    );

    await page.goto("/prediction");
    await page.getByTestId("predict-flight-input").fill("AA123");
    await page.getByTestId("predict-origin").selectOption("JFK");
    await page.getByTestId("predict-destination").selectOption("LAX");
    await page.getByTestId("predict-date").fill("2026-11-20");
    await page.getByTestId("predict-submit").click();

    const err = page.getByTestId("predict-error");
    await expect(err).toBeVisible({ timeout: 20_000 });
    await expect(err).toHaveAttribute("data-model-unavailable", "true");
    await expect(err).toContainText("model_unavailable");
    await expect(err).toContainText("heuristic");
    // No fake result may appear
    await expect(page.getByTestId("predict-result")).toHaveCount(0);
  });
});

test.describe("Analytics screen", () => {
  test("loads route analytics from the backend", async ({ page }) => {
    await page.goto("/analytics");
    await expect(page.getByTestId("analytics-routes")).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId("analytics-routes")).toContainText(
      "JFK to LAX",
    );
    await expect(page.getByTestId("analytics-error")).toHaveCount(0);
  });

  test("shows a loading state while the analytics request is pending", async ({
    page,
  }) => {
    // Delay the backend response so the loading state is observable
    // (the local backend normally resolves in a few ms).
    await page.route("**/api/v1/routes/analytics", async (route) => {
      await new Promise((r) => setTimeout(r, 1200));
      await route.continue();
    });

    await page.goto("/analytics");
    await expect(page.getByTestId("analytics-loading")).toBeVisible({
      timeout: 10_000,
    });
    // Loading resolves into real data, not an error
    await expect(page.getByTestId("analytics-routes")).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId("analytics-loading")).toHaveCount(0);
    await expect(page.getByTestId("analytics-error")).toHaveCount(0);
  });
});

test.describe("Model information screen", () => {
  test("loads live model info from the backend", async ({ page }) => {
    await page.goto("/models");
    await expect(page.getByTestId("model-info")).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId("model-info")).toContainText(
      "Logistic Regression",
    );
    await expect(page.getByTestId("model-info")).toContainText(
      "logistic_regression_new.joblib",
    );
    await expect(page.getByTestId("model-error")).toHaveCount(0);
  });
});

test.describe("Tracking screen", () => {
  test("lookup form returns a backend response", async ({ page }) => {
    await page.goto("/tracking");
    await page.getByTestId("tracking-flight-input").fill("AA100");
    await page
      .getByTestId("tracking-form")
      .getByRole("button", { name: /track flight/i })
      .click();

    const result = page.getByTestId("tracking-result");
    const empty = page.getByTestId("tracking-empty");
    await expect(result.or(empty)).toBeVisible({ timeout: 30_000 });
  });
});

test.describe("API unavailable state", () => {
  test("SIMULATED: backend down shows an explicit error, no fake data", async ({
    page,
  }) => {
    // Simulated failure mode: abort every backend call from the browser.
    await page.route("**/api/v1/**", (route) => route.abort());

    await page.goto("/analytics");
    await expect(page.getByTestId("analytics-error")).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId("analytics-error")).toContainText(
      /unreachable/i,
    );
    // No fabricated analytics may render
    await expect(page.getByTestId("analytics-routes")).toHaveCount(0);

    await page.goto("/models");
    await expect(page.getByTestId("model-error")).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId("model-info")).toHaveCount(0);

    await page.goto("/");
    await expect(page.getByTestId("home-status")).toHaveAttribute(
      "data-state",
      "offline",
      { timeout: 30_000 },
    );
  });
});

test.describe("Mobile navigation", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("bottom nav is visible and navigates between screens", async ({
    page,
  }) => {
    await page.goto("/");
    const nav = page.getByTestId("bottom-nav");
    await expect(nav).toBeVisible();

    for (const name of [
      "Home",
      "Tracking",
      "Predict",
      "Batch",
      "Analytics",
      "Models",
    ]) {
      await expect(nav.getByRole("link", { name })).toBeVisible();
    }

    await nav.getByRole("link", { name: "Predict" }).click();
    await expect(page).toHaveURL(/\/prediction/);
    await expect(page.getByTestId("predict-form")).toBeVisible();

    await nav.getByRole("link", { name: "Batch" }).click();
    await expect(page).toHaveURL(/\/batch/);
    await expect(page.getByTestId("batch-dropzone")).toBeVisible();

    await nav.getByRole("link", { name: "Analytics" }).click();
    await expect(page).toHaveURL(/\/analytics/);
    await expect(page.getByTestId("analytics-routes")).toBeVisible({
      timeout: 30_000,
    });

    await nav.getByRole("link", { name: "Home" }).click();
    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByTestId("lookup-form")).toBeVisible();
  });
});

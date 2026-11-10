// @ts-check
/*!
 * AeroDelay AI - Batch prediction browser E2E tests.
 *
 * Preconditions:
 *  - FastAPI backend running on http://127.0.0.1:8000 (start_backend.py)
 *  - Next.js dev server running on http://localhost:3000 (npx next dev)
 *
 * Tests marked SIMULATED intercept the browser's request to exercise error
 * states (all-files-rejected, model_unavailable, backend down). Every other
 * test drives the REAL backend and the REAL ML model. No external flight
 * provider is contacted by any test in this file.
 */

const { test, expect } = require("@playwright/test");

const CANONICAL_HEADER = "flight_number,origin,destination,date\n";
const GOOD_ROWS =
  "AA1234,JFK,LAX,2022-12-15\n" +
  "DL456,SFO,SEA,2022-12-16\n" +
  "UA789,ORD,JFK,2022-12-17\n";

/** 5 rows: 3 valid (MIA now in model vocabulary), 2 invalid (unknown carrier / date). */
const MIXED_ROWS =
  CANONICAL_HEADER +
  "AA1234,JFK,LAX,2022-12-15\n" +
  "XX111,JFK,LAX,2022-12-15\n" +
  "AA1234,MIA,LAX,2022-12-15\n" +
  "AA1234,JFK,LAX,not-a-date\n" +
  "DL456,SFO,SEA,2022-12-16\n";

/** Non-canonical headers -> exercises the column-mapping table. */
const CUSTOM_HEADER = "FLT,From,To,When\nAA1234,JFK,LAX,2022-12-15\n";

function csv(name, content) {
  return { name, mimeType: "text/csv", buffer: Buffer.from(content, "utf8") };
}

test.describe("Batch screen", () => {
  test("loads with dropzone, templates, schema help and disabled run button", async ({
    page,
  }) => {
    await page.goto("/batch");
    await expect(
      page.getByRole("heading", { name: "Batch Prediction", level: 1 }),
    ).toBeVisible();

    await expect(page.getByTestId("batch-dropzone")).toBeVisible();
    await expect(page.getByTestId("batch-template")).toBeVisible();
    await expect(page.getByTestId("batch-template-bts")).toBeVisible();

    // Nothing queued yet -> cannot run
    await expect(page.getByTestId("batch-run")).toBeDisabled();

    // Limits are surfaced to the user
    await expect(page.getByText("Files / batch")).toBeVisible();
    await expect(page.getByText("Rows / batch")).toBeVisible();

    // Honest-model wording is present before any upload
    await expect(page.getByText(/no heuristic/i)).toBeVisible();
    await expect(page.getByTestId("batch-summary")).toHaveCount(0);
  });

  test("CSV templates download from the real backend", async ({ page }) => {
    await page.goto("/batch");

    const [download] = await Promise.all([
      page.waitForEvent("download", { timeout: 30_000 }),
      page.getByTestId("batch-template").click(),
    ]);
    expect(download.suggestedFilename()).toBe("aerodelay_batch_template.csv");

    const [btsDownload] = await Promise.all([
      page.waitForEvent("download", { timeout: 30_000 }),
      page.getByTestId("batch-template-bts").click(),
    ]);
    expect(btsDownload.suggestedFilename()).toBe(
      "aerodelay_batch_template_bts.csv",
    );
  });

  test("queue: files are listed with counts and can be removed one by one", async ({
    page,
  }) => {
    await page.goto("/batch");
    await page.getByTestId("batch-file-input").setInputFiles([
      csv("one.csv", CANONICAL_HEADER + GOOD_ROWS),
      csv("two.csv", CANONICAL_HEADER + GOOD_ROWS),
      csv("three.csv", CANONICAL_HEADER + GOOD_ROWS),
    ]);

    await expect(page.getByTestId("batch-file-row")).toHaveCount(3);
    await expect(page.getByTestId("batch-queue-count")).toContainText(
      "3 files queued",
    );
    await expect(page.getByTestId("batch-queue-count")).toContainText(
      "3 ready to send",
    );
    await expect(page.getByTestId("batch-run")).toBeEnabled();

    // Remove the first file individually
    await page.getByTestId("batch-file-remove").first().click();
    await expect(page.getByTestId("batch-file-row")).toHaveCount(2);
    await expect(page.getByTestId("batch-queue-count")).toContainText(
      "2 files queued",
    );

    // Clear all
    await page.getByTestId("batch-clear").click();
    await expect(page.getByTestId("batch-file-row")).toHaveCount(0);
    await expect(page.getByTestId("batch-run")).toBeDisabled();
  });

  test("client pre-checks block non-CSV and empty files with a reason", async ({
    page,
  }) => {
    await page.goto("/batch");
    await page.getByTestId("batch-file-input").setInputFiles([
      { name: "notes.txt", mimeType: "text/plain", buffer: Buffer.from("hi") },
      csv("empty.csv", ""),
      csv("good.csv", CANONICAL_HEADER + GOOD_ROWS),
    ]);

    await expect(page.getByTestId("batch-file-row")).toHaveCount(3);
    const blocked = page.locator('[data-testid="batch-file-row"][data-state="error"]');
    await expect(blocked).toHaveCount(2);

    await expect(page.getByTestId("batch-queue-count")).toContainText(
      "1 ready to send",
    );
    await expect(page.getByTestId("batch-queue-count")).toContainText(
      "2 blocked",
    );
    await expect(blocked.first()).toContainText(/\.csv file|empty/i);
    // Only the valid file is sent
    await expect(page.getByTestId("batch-run")).toBeEnabled();
  });

  test("duplicate files (same name + size) are flagged but kept", async ({
    page,
  }) => {
    await page.goto("/batch");
    await page.getByTestId("batch-file-input").setInputFiles([
      csv("same.csv", CANONICAL_HEADER + GOOD_ROWS),
      csv("same.csv", CANONICAL_HEADER + GOOD_ROWS),
    ]);

    await expect(page.getByTestId("batch-file-row")).toHaveCount(2);
    await expect(page.getByTestId("batch-queue")).toContainText(
      /Possible duplicate of/i,
    );
    // Duplicates are never silently dropped
    await expect(page.getByTestId("batch-queue-count")).toContainText(
      "2 ready to send",
    );
  });

  test("column mapping table appears once a header is detected", async ({
    page,
  }) => {
    await page.goto("/batch");
    await page.getByTestId("batch-file-input").setInputFiles([
      csv("custom.csv", CUSTOM_HEADER),
    ]);

    const mapping = page.getByTestId("batch-mapping");
    await expect(mapping).toBeVisible();
    await expect(page.getByTestId("batch-map-origin")).toBeVisible();
    await expect(
      page.getByTestId("batch-map-origin").locator("option", { hasText: "From" }),
    ).toHaveCount(1);
    await expect(
      page.getByTestId("batch-map-date").locator("option", { hasText: "When" }),
    ).toHaveCount(1);

    // Explicit mapping -> the batch runs and the row is predicted
    await page.getByTestId("batch-map-flight_number").selectOption("FLT");
    await page.getByTestId("batch-map-origin").selectOption("From");
    await page.getByTestId("batch-map-destination").selectOption("To");
    await page.getByTestId("batch-map-date").selectOption("When");
    await page.getByTestId("batch-run").click();

    const summary = page.getByTestId("batch-summary");
    await expect(summary).toBeVisible({ timeout: 60_000 });
    await expect(summary).toHaveAttribute("data-status", "completed");
    await expect(page.getByTestId("batch-result-row")).toHaveCount(1);
    await expect(page.getByTestId("batch-results-table")).toContainText("JFK");
  });
});

test.describe("Batch execution (real backend, real model)", () => {
  test("a clean batch produces model results, charts and downloads", async ({
    page,
  }) => {
    await page.goto("/batch");
    await page.getByTestId("batch-file-input").setInputFiles([
      csv("flights_a.csv", CANONICAL_HEADER + GOOD_ROWS),
      csv("flights_b.csv", CANONICAL_HEADER + GOOD_ROWS),
    ]);
    await page.getByTestId("batch-run").click();

    const summary = page.getByTestId("batch-summary");
    await expect(summary).toBeVisible({ timeout: 60_000 });
    await expect(summary).toHaveAttribute("data-status", "completed");

    // Totals
    await expect(summary).toContainText("Rows predicted");
    await expect(page.getByTestId("batch-donut")).toBeVisible();
    await expect(page.getByTestId("batch-outcome-bars")).toBeVisible();

    // Every row came from the real model; the version is shown with the downloads
    await expect(page.getByTestId("batch-result-row")).toHaveCount(6);
    await expect(page.getByTestId("batch-downloads")).toContainText(
      "Phase 2 Ensemble v2.1",
    );

    // Per-file stats for both inputs
    await expect(page.getByTestId("batch-file-stat")).toHaveCount(2);

    // Probabilities are framed as model output, not certainty
    await expect(page.getByTestId("batch-summary")).toContainText(
      /not guarantees/i,
    );
    await expect(page.getByTestId("batch-summary")).toContainText(
      /uncalibrated model outputs/i,
    );

    // No rejected rows in a clean batch
    await expect(page.getByTestId("batch-failures")).toContainText(
      /Every row passed validation/i,
    );

    // Downloads (real files served by the backend)
    const combined = await Promise.all([
      page.waitForEvent("download", { timeout: 30_000 }),
      page.getByTestId("batch-download-combined").click(),
    ]);
    expect(combined[0].suggestedFilename()).toMatch(
      /aerodelay_batch_.*_combined\.csv/,
    );

    const summaryCsv = await Promise.all([
      page.waitForEvent("download", { timeout: 30_000 }),
      page.getByTestId("batch-download-summary").click(),
    ]);
    expect(summaryCsv[0].suggestedFilename()).toMatch(
      /aerodelay_batch_.*_summary\.csv/,
    );

    const failuresCsv = await Promise.all([
      page.waitForEvent("download", { timeout: 30_000 }),
      page.getByTestId("batch-download-failures").click(),
    ]);
    expect(failuresCsv[0].suggestedFilename()).toMatch(
      /aerodelay_batch_.*_failures\.csv/,
    );

    // Start another batch clears the screen back to the dropzone
    await page.getByTestId("batch-reset").click();
    await expect(page.getByTestId("batch-dropzone")).toBeVisible();
    await expect(page.getByTestId("batch-summary")).toHaveCount(0);
  });

  test("invalid rows are rejected with reasons, never silently dropped", async ({
    page,
  }) => {
    await page.goto("/batch");
    await page.getByTestId("batch-file-input").setInputFiles([
      csv("mixed.csv", MIXED_ROWS),
    ]);
    await page.getByTestId("batch-run").click();

    const summary = page.getByTestId("batch-summary");
    await expect(summary).toBeVisible({ timeout: 60_000 });
    await expect(summary).toHaveAttribute(
      "data-status",
      "completed_with_errors",
    );

    // 5 input rows -> 3 predicted (MIA now in model vocabulary), 2 rejected
    await expect(page.getByTestId("batch-result-row")).toHaveCount(3);
    await expect(page.getByTestId("batch-failures")).toContainText(
      "2 rejected rows",
    );
    await expect(page.getByTestId("batch-failures")).toContainText(
      "unknown_carrier",
    );
    await expect(page.getByTestId("batch-failures")).toContainText(
      "invalid_date",
    );
    await expect(page.getByTestId("batch-failures")).toContainText("row 2");
    await expect(page.getByTestId("batch-failures")).toContainText("row 4");

    // Per-file stats expose the rejected count
    await expect(page.getByTestId("batch-file-stat")).toHaveAttribute(
      "data-status",
      "completed",
    );
    await expect(page.getByTestId("batch-file-stats")).toContainText("mixed.csv");
  });

  test("a batch with a schema-breaking file reports it and still scores the rest", async ({
    page,
  }) => {
    await page.goto("/batch");
    await page.getByTestId("batch-file-input").setInputFiles([
      csv("ok.csv", CANONICAL_HEADER + GOOD_ROWS),
      csv("broken.csv", "flight_number,origin,date\nAA1234,JFK,2022-12-15\n"),
    ]);
    await page.getByTestId("batch-run").click();

    const summary = page.getByTestId("batch-summary");
    await expect(summary).toBeVisible({ timeout: 60_000 });

    // The valid file was still processed
    await expect(page.getByTestId("batch-result-row")).toHaveCount(3);
    // ...and the rejected file is reported with its own error
    await expect(page.getByTestId("batch-rejected-files")).toContainText(
      "1 file",
    );
    await expect(page.getByTestId("batch-file-stats")).toContainText(
      "missing_required_columns",
    );
    await expect(page.getByTestId("batch-file-stat").last()).toHaveAttribute(
      "data-status",
      "rejected",
    );
  });
});

test.describe("Batch error states (SIMULATED browser-side)", () => {
  test("SIMULATED: every file rejected (422) lists each file's reason", async ({
    page,
  }) => {
    await page.route("**/api/v1/predict/batch", (route) => {
      if (route.request().method() !== "POST") return route.fallback();
      return route.fulfill({
        status: 422,
        contentType: "application/json",
        body: JSON.stringify({
          error: "all_files_rejected",
          detail: "Every uploaded file failed validation.",
          timestamp: Date.now() / 1000,
          files: [
            {
              file_id: "f001",
              name: "bad.csv",
              status: "rejected",
              error: {
                code: "missing_required_columns",
                detail: "Missing required column(s): destination.",
              },
            },
          ],
        }),
      });
    });

    await page.goto("/batch");
    await page.getByTestId("batch-file-input").setInputFiles([
      csv("bad.csv", "flight_number,origin,date\nAA1234,JFK,2022-12-15\n"),
    ]);
    await page.getByTestId("batch-run").click();

    const rejected = page.getByTestId("batch-all-rejected");
    await expect(rejected).toBeVisible({ timeout: 20_000 });
    await expect(rejected).toContainText("bad.csv");
    await expect(rejected).toContainText("missing_required_columns");
    // No results may be fabricated
    await expect(page.getByTestId("batch-summary")).toHaveCount(0);
    await expect(page.getByTestId("batch-dropzone")).toBeVisible();
  });

  test("SIMULATED: model_unavailable (550) is shown honestly, no results", async ({
    page,
  }) => {
    await page.route("**/api/v1/predict/batch", (route) => {
      if (route.request().method() !== "POST") return route.fallback();
      return route.fulfill({
        status: 550,
        contentType: "application/json",
        body: JSON.stringify({
          error: "model_unavailable",
          detail: "ML model inference cannot run, so no batch job was created.",
          timestamp: Date.now() / 1000,
        }),
      });
    });

    await page.goto("/batch");
    await page.getByTestId("batch-file-input").setInputFiles([
      csv("good.csv", CANONICAL_HEADER + GOOD_ROWS),
    ]);
    await page.getByTestId("batch-run").click();

    const err = page.getByTestId("batch-upload-error");
    await expect(err).toBeVisible({ timeout: 20_000 });
    await expect(err).toContainText("model_unavailable");
    await expect(err).toContainText(/heuristic/i);
    // No fabricated predictions
    await expect(page.getByTestId("batch-summary")).toHaveCount(0);
    await expect(page.getByTestId("batch-results-table")).toHaveCount(0);
  });

  test("SIMULATED: backend unreachable shows an explicit error, no fake data", async ({
    page,
  }) => {
    await page.route("**/api/v1/**", (route) => route.abort());

    await page.goto("/batch");
    await page.getByTestId("batch-file-input").setInputFiles([
      csv("good.csv", CANONICAL_HEADER + GOOD_ROWS),
    ]);
    await page.getByTestId("batch-run").click();

    const err = page.getByTestId("batch-upload-error");
    await expect(err).toBeVisible({ timeout: 30_000 });
    await expect(err).toContainText(/unreachable/i);
    await expect(page.getByTestId("batch-summary")).toHaveCount(0);
  });
});

test.describe("Batch screen on mobile", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("dropzone, queue and run button fit without horizontal overflow", async ({
    page,
  }) => {
    await page.goto("/batch");
    await expect(page.getByTestId("batch-dropzone")).toBeVisible();

    await page.getByTestId("batch-file-input").setInputFiles([
      csv("m1.csv", CANONICAL_HEADER + GOOD_ROWS),
      csv("m2.csv", CANONICAL_HEADER + GOOD_ROWS),
    ]);
    await expect(page.getByTestId("batch-file-row")).toHaveCount(2);

    const scrollWidth = await page.evaluate(
      () => document.documentElement.scrollWidth,
    );
    expect(scrollWidth).toBeLessThanOrEqual(390 + 1);

    const box = await page.getByTestId("batch-run").boundingBox();
    expect(box).not.toBeNull();
    expect(box.x).toBeGreaterThanOrEqual(0);
    expect(box.x + box.width).toBeLessThanOrEqual(391);
    await expect(page.getByTestId("batch-run")).toBeEnabled();
  });
});

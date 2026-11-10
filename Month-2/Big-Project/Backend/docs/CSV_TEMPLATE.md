# Batch CSV Template & Input Schema

Everything you need to prepare CSV files for the **Batch Prediction** screen
(`http://localhost:3000/batch`) or `POST /api/v1/predict/batch`.

## 1. Getting a template

| Source | How |
|---|---|
| UI | Batch screen → **CSV template** (canonical) or **BTS-style template** buttons |
| API | `GET /api/v1/predict/batch/template?style=canonical` → `aerodelay_batch_template.csv` |
| API | `GET /api/v1/predict/batch/template?style=bts` → `aerodelay_batch_template_bts.csv` |
| Repo | `templates/batch_prediction_template.csv` (canonical) |

## 2. Canonical schema

```csv
flight_number,origin,destination,date
AA1234,JFK,LAX,2022-12-15
DL456,SFO,SEA,2022-12-16
UA789,ORD,JFK,2022-12-17
```

| Column | Required | Format | Notes |
|---|---|---|---|
| `flight_number` | Yes\* | Airline code + digits, ≤10 chars, e.g. `AA1234` | \*Optional **only** if `carrier` is present |
| `carrier` | Yes\* | 2-letter IATA code, e.g. `AA` | \*Optional **only** if `flight_number` is present (carrier read from its prefix) |
| `origin` | Yes | 3-letter IATA, e.g. `JFK` | Must be one of the supported airports |
| `destination` | Yes | 3-letter IATA, e.g. `LAX` | Must be one of the supported airports |
| `date` | Yes | `YYYY-MM-DD` (also `YYYY/MM/DD`, `MM/DD/YYYY`, `YYYY-MM-DD HH:MM`) | Normalised to `YYYY-MM-DD` in results |

At least one of `flight_number` / `carrier` must be present — a file with
neither is rejected with `missing_required_columns`.

## 3. Supported values

The served model was trained on a restricted vocabulary. Values outside it are
**rejected with a reason, never remapped or silently coerced**.

- **Carriers (7):** `AA` `DL` `UA` `B6` `WN` `F9` `AS`
- **Airports (5):** `JFK` `LAX` `SFO` `ORD` `SEA`

## 4. BTS-style schema

For raw BTS On-Time Performance extracts, `style=bts` gives:

```csv
Year,Month,DayOfMonth,Reporting_Airline,Origin,Dest
2022,12,15,AA,JFK,LAX
2022,12,16,DL,SFO,SEA
2022,12,17,UA,ORD,JFK
```

BTS multi-column construction is applied automatically (only when the single
column is absent):

- `Year` + `Month` + `DayOfMonth` (or `Day`) → `date`
- `Reporting_Airline` + `Flight_Number_Reporting_Airline` → `flight_number`

## 5. Column aliases (auto-detected)

Header matching is case-insensitive and ignores separators. If several columns
match the same field, the **first** one wins and a warning is recorded.

| Canonical | Recognised aliases (examples) |
|---|---|
| `flight_number` | `FlightNumber`, `FlightNo`, `Flight`, `Flight_ID`, `Flight_Number_Reporting_Airline`, `IATA_Flight_Number` |
| `carrier` | `Airline`, `AirlineCode`, `IATACode`, `OperatingAirline`, `MarketingAirline`, `Reporting_Airline` |
| `origin` | `Origin_IATA`, `OriginAirport`, `DepartureAirport`, `From`, `ORIG` |
| `destination` | `Dest`, `Dest_IATA`, `DestinationAirport`, `ArrivalAirport`, `To` |
| `date` | `FlightDate`, `DepDate`, `DepartureDate`, `CalDate`, `FlightDay`, `ScheduleDate` |

**Manual mapping:** after a file is queued, the Batch screen reads its header
and offers a mapping table. One global mapping is sent with the batch and
applied to **every** file; a file missing a manually mapped column is rejected
with a clear message (nothing is guessed).

## 6. Label / outcome columns are never model inputs

Columns that look like the prediction target are recognised and **excluded**
from the feature vector (they may be present in your CSV; they are never fed
to the model):

`DepDelay15`, `DepDel15`, `Delay15`, `Delayed15`, `IsDelayed`, `DepDelay`,
`DepDelayMinutes`, `DepDelayGroup`, `ArrDelay`, `ArrDelayMinutes`,
`ArrDel15`, `ArrDelay15`, `Cancelled`, `Diverted`, `Label`, `Target`, `Y`

Encountering one produces a warning, not a rejection.

## 7. File-level rules (each file is validated individually)

| Rule | Behaviour |
|---|---|
| Extension | Must be `.csv` — otherwise `unsupported_extension` |
| Encoding | `UTF-8` (with/without BOM) and `CP1252` accepted. UTF-16 → `encoding_error` with an actionable message; binary content → `binary_content` |
| Size | ≤ 10 MB per file (`file_too_large`) |
| Empty | 0 bytes, header-only or no data → `empty_file` |
| Headers | Parseable, no empty names (`invalid_headers`), no duplicates (`duplicate_headers`) |
| Required columns | Missing → `missing_required_columns` (lists exactly which) |
| Rows | ≤ 50,000 per file (`too_many_rows`); malformed CSV → `unreadable_csv` with the line number |
| Duplicates | Identical files are **kept** and flagged (`Duplicate file content…` warning); exact duplicate rows are **kept** and counted in a warning — nothing is silently removed |

## 8. Row-level rules

Each row is validated independently. Invalid rows are **rejected with a
column + code + message** and written to the downloadable failure ledger;
valid rows in the same file are still predicted.

| Code | Meaning |
|---|---|
| `missing_value` | Required value empty (`flight_number`, `origin`, `destination`, `date`) |
| `unknown_carrier` | Carrier outside the 7 supported codes |
| `unknown_airport` | Origin/destination outside the 5 supported airports |
| `invalid_flight_number` | Not `code + digits`, or > 10 characters |
| `flight_number_mismatch` | `carrier` column disagrees with the flight-number prefix |
| `invalid_date` | Date not in a recognised format |
| `formula_input` | Value shaped like a spreadsheet formula (e.g. `=cmd\|…`) — rejected instead of exported |

Nothing is ever truncated: every input row ends up either in the results CSV
or in the failures CSV.

## 9. Limits (enforced server-side, echoed in every status response)

| Limit | Value |
|---|---|
| Files per batch | 200 |
| Size per file | 10 MB |
| Size per batch | 100 MB |
| Rows per file | 50,000 |
| Rows per batch | 500,000 |
| Inference chunk size | 500 rows |
| Results page size | default 100, max 500 |
| Failure ledger in API responses | first 500 (full list via failures CSV) |
| Job retention (TTL) | 1 hour (temp files cleaned on delete, expiry or process exit) |

The Batch screen shows the same limits before you upload anything.

## 10. Encoding & CSV dialect

- UTF-8 with or without BOM, and CP1252, are decoded automatically; the
  detected encoding is reported per file.
- Standard RFC-4180 quoting (`"…"`, doubled `""` for literal quotes) is
  supported; the delimiter is `,`.
- Cells beginning with `=`, `+`, `-`, `@`, tab or CR are neutralised on export
  (CSV-injection guard) and formula-shaped inputs are rejected on import.

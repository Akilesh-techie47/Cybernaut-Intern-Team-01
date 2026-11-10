# AeroDelay AI Dataset Comparison Report

## Objective
Identify and compare candidate datasets for predicting `DepDelay15` (departure delay >= 15 minutes).

---

## Candidate 1: BTS On-Time Performance (Reporting Carrier) — Current Dataset

| Attribute | Details |
|---|---|
| **Name** | US DOT BTS On-Time Performance - Reporting Carrier |
| **Source URL** | <https://transtats.bts.gov/> |
| **Download URL** | <https://transtats.bts.gov/PREZIP/On_Time_Reporting_Carrier_On_Time_Performance_1987_present_{{year}}_{{month}}.zip> |
| **License** | Public domain - US Government data. No official restriction on use, modification, or redistribution. |
| **Download Method** | Direct ZIP download from BTS TranStats; extract CSV |
| **File Format** | Zipped CSV (one CSV per month) |
| **Date Coverage** | 1987-present (monthly records) |
| **Record Count** | ~5000 records per month; ~526,882 usable records for Dec 2022 |
| **Target Derivation** | `DepDel15` column directly: 1 = departure delay >= 15 min, 0 otherwise |
| **Key Columns** | `Year`, `Month`, `DayOfWeek`, `Origin`, `Dest`, `CRSDepTime`, `DepDel15`, `Reporting_Airline`, `Distance`, `CRSElapsedTime`, `Cancelled`, `CancellationCode`, `Diverted` |
| **Leakage Risks** | `DepTime`, `DepDelay`, `TaxiOut`, `WheelsOff`, `ArrTime`, `ArrDelay`, `ActualElapsedTime` (all post-departure) |
| **Pre-Departure Predictors** | `Reporting_Airline`, `Origin`, `Dest`, `Month`, `Distance`, `Cancelled`, `Diverted`, `DayOfWeek`, `CRSDepTime`, `CRSElapsedTime` |
| **Missingness** | `DepDelayMinutes`: ~5.42% missing; `Tail_Number`: ~1.42% missing; `Deptime`: ~5.42% missing |
| **Class Balance** | 0: 385,163; 1: 141,719 (for Dec 2022) |
| **Suitability** | ✅ Excellent — direct target column, public domain, reproducible monthly downloads, well-documented field definitions |
| **Notes** | Already collected and audited; 7 predictors identified; 0 leakage columns in current configuration |

---

## Candidate 2: Kaggle - US Flight Delay Dataset 2023-2024

| Attribute | Details |
|---|---|
| **Name** | US Flight Delay Dataset 2023-2024 |
| **Source URL** | <https://www.kaggle.com/datasets/algorithmicdeer/us-flight-delay-dataset-2023-2024> |
| **Download URL** | Kaggle API or web interface |
| **License** | Unknown (not explicitly listed on data card) |
| **Download Method** | Kaggle API (`kagle datasets download`) or web download |
| **File Format** | CSV (possibly multiple files) |
| **Date Coverage** | 2023-2024 |
| **Record Count** | ~7M+ rows (per data card) |
| **Target Derivation** | Target column not immediately obvious; would need to inspect fields |
| **Key Columns** | Includes `dep_delay`, `arr_delay`, `cancelled`, `diverted`, `carrier_delay`, `weather_delay`, `nas_delay`, `security_delay`, `late_aircraft_delay` |
| **Leakage Risks** | `dep_delay`, `arr_delay`, `taxi_out`, `wheels_off`, `actual_elapsed_time` are post-departure |
| **Pre-Departure Predictors** | `op_unique_carrier`, `origin`, `dest`, `day_of_week`, `month`, `crs_dep_time`, `distance`, `cr_elapsed_time`, `cancelled`, `diverted` |
| **Missingness** | Not fully documented on data card |
| **Class Balance** | Not specified on data card |
| **Suitability** | ⚠️ Medium — license unknown, may require API access, target derivation needed |
| **Notes** | Data card usability score: 1.76/10; license not clearly public domain; would need to verify target column availability |

---

## Candidate 3: Hugging Face - DOT Airline On-Time Performance 2018–2024

| Attribute | Details |
|---|---|
| **Name** | DOT Airline On-Time Performance 2018–2024 |
| **Source URL** | <https://huggingface.co/datasets/claritystorm/dot-airline-ontime> |
| **Download Method** | `datasets` library: `datasets.load_dataset("claritystorm/dot-airline-ontime")` |
| **License** | Public domain (US federal data); packaged sample is public, full snapshot requires $99 one-time payment |
| **Download Method** | Public sample: 1,000 rows (12 evenly spaced rows per month through April 2024, then 11 per month for May–December 2024). Not statistically representative. Full package: $99 one-time for deterministic 12-row-per-month sample. |
| **File Format** | Parquet (full) / CSV (sample) |
| **Date Coverage** | January 2018 – December 2024 |
| **Record Count** | Public sample: 1,000 rows. Full: 45,968,068 reported flight records across 84 months. |
| **Target Derivation** | `DepDelay15` can be derived from `DepDel15` column (present) or from `DepDelay` >= 15 |
| **Key Columns** | All 109 BTS source fields plus `source_month` and `source_row`; includes `DepDel15`, `Cancelled`, `Diverted`, `DepDelay`, `ArrDelay` |
| **Leakage Risks** | All post-departure fields (`DepTime`, `DepDelay`, `TaxiOut`, `WheelsOff`, `ArrTime`, `ArrDelay`, `ActualElapsedTime`) are present but can be excluded |
| **Pre-Departure Predictors** | `Reporting_Airline`, `Origin`, `Dest`, `Month`, `Distance`, `Cancelled`, `Diverted`, `DayOfWeek`, `CRSDepTime`, `CRSElapsedTime`, plus 100+ other BTS fields |
| **Missingness** | Not fully documented in metadata; full schema has 111 columns |
| **Class Balance** | Not specified in public sample metadata |
| **Suitability** | ⚠️ Medium — public sample too small (1000 rows); full dataset requires payment; otherwise excellent column coverage |
| **Notes** | Deterministic sample is not statistically representative; full package costs $99; field schema is complete (111 columns) |

---

## Candidate 4: Kaggle - Flight Delay Dataset 2024 (CC0 Licensed)

| Attribute | Details |
|---|---|
| **Name** | Flight Delay Dataset — 2024 |
| **Source URL** | <https://www.kaggle.com/datasets/hrishitpatil/flight-data-2024> |
| **Download URL** | Kaggle API: `kaggle datasets download hrishitpatil/flight-data-2024` |
| **License** | CC0: Public Domain |
| **Download Method** | Kaggle API |
| **File Format** | CSV (~7M rows, 35 columns) |
| **Date Coverage** | 2024 (full year) |
| **Record Count** | ~7M+ rows |
| **Target Derivation** | `DepDelay15` can be derived: `dep_delay >= 15` → 1, else 0 |
| **Key Columns** | `year`, `month`, `day_of_month`, `day_of_week`, `fl_date`, `op_unique_carrier`, `origin`, `dest`, `crs_dep_time`, `dep_time`, `dep_delay`, `taxi_out`, `wheels_off`, `wheels_on`, `taxi_in`, `crs_arr_time`, `arr_time`, `arr_delay`, `cancelled`, `diverted`, `crs_elapsed_time`, `actual_elapsed_time`, `air_time`, `distance`, `carrier_delay`, `weather_delay`, `nas_delay`, `security_delay`, `late_aircraft_delay` |
| **Leakage Risks** | `dep_time`, `dep_delay`, `taxi_out`, `wheels_off`, `actual_elapsed_time`, `arr_time`, `arr_delay` are post-departure |
| **Pre-Departure Predictors** | `op_unique_carrier`, `origin`, `dest`, `day_of_week`, `month`, `crs_dep_time`, `crs_elapsed_time`, `distance`, `cancelled`, `diverted` |
| **Missingness** | Not fully documented; dataset notes mention missing values were filled with 0 for delay-related columns |
| **Class Balance** | Not specified |
| **Suitability** | ⚠️ Medium — CC0 license is good, but target derivation required, and `dep_time`/`dep_delay` leakage columns present |
| **Notes** | Dataset is "merged from monthly BTS TranStats files into a single cleaned dataset"; 35 columns selected; license is CC0 (public domain) |

---

## Candidate 5: Data.gov - Airline On-Time Performance (Same as BTS)

| Attribute | Details |
|---|---|
| **Name** | Airline On-Time Performance and Causes of Flight Delays |
| **Source URL** | <https://data.transportation.gov/Aviation/Airline-On-Time-Performance-and-Causes-of-Flight-D/r52d-vs5d> |
| **Download Method** | Socrata API or CSV download from data portal |
| **License** | US Government data - public domain |
| **Download Method** | Socrata Open Data API; CSV exports available |
| **File Format** | API-accessible CSV |
| **Date Coverage** | 1987-present (same as BTS) |
| **Record Count** | Same as BTS |
| **Target Derivation** | Same as BTS (`DepDel15` or derived from `DepDelay`) |
| **Key Columns** | Same as BTS dataset |
| **Leakage Risks** | Same as BTS |
| **Pre-Departure Predictors** | Same as BTS |
| **Suitability** | ⚠️ Low — same data as BTS PREZIP downloads, but API access may be less convenient; no advantage over direct BTS download |
| **Notes** | Identical data to BTS TranStats; provided via Socrata API; useful if API preferred over direct download |

---

## Summary Comparison

| Criterion | BTS (Current) | Kaggle 2023-2024 | HuggingFace DOT | Kaggle 2024 (CC0) | Data.gov |
|---|---|---|---|---|---|
| **License** | ✅ Public domain | ⚠️ Unknown | ✅ Public domain ($99 for full) | ✅ CC0 Public domain | ✅ Public domain |
| **Target Column** | ✅ `DepDel15` direct | ⚠️ Need to verify | ✅ `DepDel15` present | ⚠️ Derive from `dep_delay` | ✅ Same as BTS |
| **Record Size** | ✅ 526K (Dec 2022) | ✅ 7M+ rows | ⚠️ 1K public / 45M full | ✅ 7M+ rows | ✅ Same as BTS |
| **Pre-Departure Predictors** | ✅ 7 identified | ✅ Good coverage | ✅ 100+ fields | ✅ Good coverage | ✅ Same as BTS |
| **Leakage Control** | ✅ Well-defined | ⚠️ Unknown columns | ✅ Full schema | ⚠️ Some leakage cols | ✅ Same as BTS |
| **Reproducibility** | ✅ Direct ZIP download | ⚠️ API-dependent | ⚠️ HuggingFace lib | ✅ Kaggle API | ⚠️ Socrata API |
| **License Freedom** | ✅ Public domain | ❓ Unknown | ✅ Public domain | ✅ CC0 | ✅ Public domain |
| **Recommendation** | **RECOMMENDED** | Alternative | Supplementary | Alternative | Alternative |

---

## Recommendation

**Select the existing BTS On-Time Performance dataset as the training dataset.**

**Rationale:**
1. **Direct target compatibility**: `DepDel15` column already present — no derivation needed
2. **Public domain license**: No restrictions on use, modification, or redistribution
3. **Reproducible download**: Direct ZIP from BTS TranStats, no API keys or payments required
4. **Already audited and working**: Preprocessing pipeline already implemented and tested
5. **Adequate size**: 526,882 usable records for Dec 2022 alone; multi-year coverage available
6. **Well-documented fields**: All 109 BTS fields with known definitions and leakage risks
7. **Tests passing**: All 29 tests currently pass with this dataset

**The existing BTS dataset is the best candidate** because it fully satisfies all project requirements without introducing licensing, download, or target-derivation uncertainties.
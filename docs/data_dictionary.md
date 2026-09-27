# Data Dictionary — SMART Parking Solutions

## Bronze Layer (Raw)

### `locations.parquet`
| Column | Type | Description |
|--------|------|-------------|
| location_id | string | Unique ID e.g. LOC-001 |
| location_name | string | Human-readable name |
| city | string | Pakistani city (10 cities) |
| province | string | Punjab / Sindh / KPK / Balochistan / Capital Territory |
| neighborhood | string | Sub-area e.g. DHA, Gulberg, Clifton |
| zone_type | string | Commercial / Residential / Hospital / Market / Corporate / Educational / Religious / Transit Hub |
| total_slots | int | Total parking capacity |
| floors | int | Number of floors (multi-storey) |
| has_anpr | bool | ANPR cameras installed |
| has_ev_charging | bool | EV charging points available |
| has_valet | bool | Valet service available |
| is_covered | bool | Covered/indoor parking |
| hourly_rate_pkr | float | Base rate per hour (PKR) |
| monthly_pass_pkr | float | Monthly season pass rate (PKR) |
| latitude | float | Approximate latitude |
| longitude | float | Approximate longitude |
| opening_hour | int | Opening time (0 = 24h) |
| closing_hour | int | Closing time (0 = 24h) |
| created_at | date | Record creation date |

### `vehicles.parquet`
| Column | Type | Description |
|--------|------|-------------|
| vehicle_id | string | Unique ID e.g. VEH-00001 |
| plate_number | string | Pakistani plate format ABC-1234 or LHR-123 |
| vehicle_type | string | Suzuki Alto / Honda City / SUV / Motorbike / Rickshaw / Bus etc. |
| color | string | Vehicle colour |
| make_year | int | Manufacturing year |
| is_blacklisted | bool | Flag for blacklisted/stolen vehicles |
| base_rate_pkr | float | Vehicle-class base rate (PKR/hr) |
| registered_city | string | City of vehicle registration |

### `customers.parquet`
| Column | Type | Description |
|--------|------|-------------|
| customer_id | string | Unique ID e.g. CUST-00001 |
| full_name | string | Customer full name (Pakistani names) |
| cnic | string | CNIC format: PPPPP-NNNNNNN-C |
| phone | string | Pakistani mobile: 03XX-XXXXXXX |
| email | string | Email address |
| city | string | Home city |
| gender | string | Male / Female |
| age | int | Age in years |
| has_season_pass | bool | Active season pass holder |
| season_pass_expiry | date | Season pass expiry date (nullable) |
| loyalty_points | int | Accumulated loyalty points |
| preferred_payment | string | Cash / JazzCash / EasyPaisa / Card |
| registration_date | date | Account registration date |

### `parking_transactions.parquet`
| Column | Type | Description |
|--------|------|-------------|
| transaction_id | string | Unique ID e.g. TXN-0000001 |
| location_id | string | FK → locations |
| vehicle_id | string | FK → vehicles |
| customer_id | string | FK → customers (nullable for anonymous) |
| slot_id | string | Specific slot e.g. LOC-001-S042 |
| entry_time | timestamp | Entry datetime (PKT UTC+5) |
| exit_time | timestamp | Exit datetime (PKT UTC+5) |
| duration_minutes | int | Parking duration in minutes |
| fee_pkr | float | Total fee charged (PKR) |
| payment_method | string | Cash / JazzCash / EasyPaisa / Card |
| is_season_pass | bool | Transaction billed via season pass |
| vehicle_type | string | Denormalised vehicle type |
| entry_date | date | Entry date (derived) |
| entry_hour | int | Hour of entry 0-23 |
| day_of_week | int | 0=Monday … 6=Sunday |

### `anpr_events.parquet`
| Column | Type | Description |
|--------|------|-------------|
| anpr_event_id | string | Unique ANPR event ID |
| location_id | string | FK → locations |
| transaction_id | string | FK → transactions (nullable) |
| vehicle_id | string | FK → vehicles (nullable) |
| camera_id | string | Camera identifier e.g. CAM-LOC-001-02 |
| event_type | string | ENTRY / EXIT |
| scan_time | timestamp | Scan timestamp |
| confidence_score | float | OCR confidence 0.5–1.0 |
| is_blacklisted_hit | bool | Plate matched blacklist |

### `sensor_events.parquet`
| Column | Type | Description |
|--------|------|-------------|
| sensor_event_id | string | Unique sensor event ID |
| slot_id | string | Parking slot identifier |
| location_id | string | FK → locations |
| status | string | OCCUPIED / FREE |
| timestamp | timestamp | Sensor ping timestamp |
| battery_pct | int | Sensor battery percentage |

### `violations.parquet`
| Column | Type | Description |
|--------|------|-------------|
| violation_id | string | Unique violation ID e.g. VIO-000001 |
| transaction_id | string | FK → transactions |
| location_id | string | FK → locations |
| vehicle_id | string | FK → vehicles |
| violation_type | string | Overstay / No Ticket / Blacklisted Plate / Wrong Zone / Unauthorized Parking / Double Parking |
| violation_time | timestamp | When violation was recorded |
| fine_pkr | float | Fine amount (PKR) |
| fine_paid | bool | Whether fine was paid |
| resolved | bool | Whether case was resolved |

### `staff_shifts.parquet`
| Column | Type | Description |
|--------|------|-------------|
| shift_id | string | Unique shift ID |
| location_id | string | FK → locations |
| staff_name | string | Employee name |
| role | string | Security Guard / Cashier / Valet / Supervisor |
| shift_type | string | Morning / Evening / Night |
| shift_start | timestamp | Shift start time |
| shift_end | timestamp | Shift end time |
| week_start | date | Week start date |

---

## Silver Layer (Cleaned)

### `silver_fact.parquet` — Core fact table
All Bronze transaction columns plus:
| Column | Type | Description |
|--------|------|-------------|
| location_name | string | Denormalised from locations |
| city | string | Denormalised |
| province | string | Denormalised |
| neighborhood | string | Denormalised |
| zone_type | string | Denormalised |
| total_slots | int | Denormalised |
| hourly_rate_pkr | float | Denormalised |
| has_anpr | bool | Denormalised |
| has_valet | bool | Denormalised |
| plate_number | string | Joined from vehicles |
| vehicle_color | string | Joined |
| make_year | int | Joined |
| is_blacklisted | bool | Joined |
| customer_name | string | Joined (nullable) |
| customer_city | string | Joined (nullable) |
| has_season_pass | bool | Joined (nullable) |
| entry_month | int | Derived 1-12 |
| entry_year | int | Derived |
| entry_week | int | Derived ISO week |
| is_ramadan | int | 0/1 seasonality flag |
| is_eid | int | 0/1 |
| is_eid_fitr | int | 0/1 |
| is_eid_adha | int | 0/1 |
| is_independence_day | int | 0/1 (Aug 14) |
| is_public_holiday | int | 0/1 |
| is_monsoon | int | 0/1 (Jul-Sep) |
| is_jummah | int | 0/1 (Friday) |
| is_weekend | int | 0/1 (Sat/Sun) |
| is_anomaly | int | 0/1 — set by anomaly detection ML |
| anomaly_score | float | Isolation Forest score (lower = more anomalous) |

---

## Gold Layer (Aggregated KPIs)

### `gold_daily_revenue.parquet`
Revenue aggregated by date × location × payment method × vehicle type. Includes seasonality flags.

### `gold_hourly_occupancy.parquet`
Transaction counts by location × hour × day-of-week × month. Includes occupancy_rate_proxy.

### `gold_peak_analysis.parquet`
Peak hour ranking per city with seasonality overlays.

### `gold_location_performance.parquet`
Per-location KPIs: total_revenue_pkr, total_transactions, avg_fee_pkr, avg_duration_minutes, violation_count, daily_utilisation_rate.

### `gold_customer_rfm.parquet`
Per-customer RFM metrics: recency_days, frequency, monetary_pkr, plus behavioural aggregates.

### `gold_violation_summary.parquet`
Violations grouped by type × location × hour × day.

### `gold_monthly_trends.parquet`
Monthly revenue + occupancy per city with mom_revenue_growth_pct.

---

## Platinum Layer (ML Features)

### `features_forecast.parquet`
Time-series features per location×date: lag features (1d, 7d, 30d), rolling averages, sin/cos encodings, seasonality flags.

### `features_classification.parquet`
Transaction-level features for violation classification. Target: `has_violation` (0/1).

### `features_clustering.parquet`
Customer-level RFM + behavioural features. Includes `cluster_id` and `cluster_name` after clustering run.

### `features_anomaly.parquet`
Transaction-level features for Isolation Forest: z-scores, flags, encoded categoricals.

### `features_pricing.parquet`
Transaction-level features for dynamic pricing GBM. Target: `actual_fee_pkr`.

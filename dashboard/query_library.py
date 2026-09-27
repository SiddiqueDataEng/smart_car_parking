"""
SQL Query Library — 50+ analytical queries organised by category.
Each entry: { "id", "category", "name", "description", "sql" }
"""

QUERY_LIBRARY = [

    # ══════════════════════════════════════════════════════════════════════════
    # REVENUE ANALYSIS  (10 queries)
    # ══════════════════════════════════════════════════════════════════════════
    {
        "id": "REV-01",
        "category": "Revenue Analysis",
        "name": "Total Revenue by City",
        "description": "Aggregate total revenue and transaction count grouped by city.",
        "sql": """
SELECT
    city,
    COUNT(*)               AS transactions,
    ROUND(SUM(fee_pkr), 0) AS total_revenue_pkr,
    ROUND(AVG(fee_pkr), 2) AS avg_fee_pkr
FROM silver_fact
GROUP BY city
ORDER BY total_revenue_pkr DESC;
""",
    },
    {
        "id": "REV-02",
        "category": "Revenue Analysis",
        "name": "Daily Revenue Trend",
        "description": "Total daily revenue across all locations for trend analysis.",
        "sql": """
SELECT
    entry_date                  AS date,
    COUNT(*)                    AS transactions,
    ROUND(SUM(fee_pkr), 0)      AS total_revenue_pkr
FROM silver_fact
GROUP BY entry_date
ORDER BY entry_date;
""",
    },
    {
        "id": "REV-03",
        "category": "Revenue Analysis",
        "name": "Month-over-Month Revenue Growth",
        "description": "MoM percentage change in revenue per city.",
        "sql": """
SELECT
    city,
    CAST(entry_year  AS INTEGER) AS year,
    CAST(entry_month AS INTEGER) AS month,
    ROUND(SUM(fee_pkr), 0)         AS revenue_pkr,
    mom_revenue_growth_pct
FROM gold_monthly_trends
ORDER BY city, year, month;
""",
    },
    {
        "id": "REV-04",
        "category": "Revenue Analysis",
        "name": "Top 10 Locations by Revenue",
        "description": "Best-performing parking locations ranked by total revenue.",
        "sql": """
SELECT
    location_name,
    city,
    zone_type,
    total_transactions,
    ROUND(total_revenue_pkr, 0)    AS total_revenue_pkr,
    ROUND(avg_fee_pkr, 2)          AS avg_fee_pkr,
    ROUND(daily_utilisation_rate, 4) AS utilisation_rate
FROM gold_location_performance
ORDER BY total_revenue_pkr DESC
LIMIT 10;
""",
    },
    {
        "id": "REV-05",
        "category": "Revenue Analysis",
        "name": "Revenue by Payment Method",
        "description": "Breakdown of revenue by JazzCash, EasyPaisa, Cash, and Card.",
        "sql": """
SELECT
    payment_method,
    COUNT(*)                   AS transactions,
    ROUND(SUM(fee_pkr), 0)     AS total_revenue_pkr,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_of_transactions
FROM silver_fact
GROUP BY payment_method
ORDER BY total_revenue_pkr DESC;
""",
    },
    {
        "id": "REV-06",
        "category": "Revenue Analysis",
        "name": "Revenue by Vehicle Type",
        "description": "Revenue contribution per vehicle category (SUV, Motorbike, etc.).",
        "sql": """
SELECT
    vehicle_type,
    COUNT(*)               AS transactions,
    ROUND(SUM(fee_pkr), 0) AS total_revenue_pkr,
    ROUND(AVG(fee_pkr), 2) AS avg_fee_pkr,
    ROUND(AVG(duration_minutes), 1) AS avg_duration_min
FROM silver_fact
GROUP BY vehicle_type
ORDER BY total_revenue_pkr DESC;
""",
    },
    {
        "id": "REV-07",
        "category": "Revenue Analysis",
        "name": "Average Revenue per Transaction per City",
        "description": "Which city generates the highest average fee per parking event?",
        "sql": """
SELECT
    city,
    COUNT(*)               AS transactions,
    ROUND(AVG(fee_pkr), 2) AS avg_fee_pkr,
    ROUND(MIN(fee_pkr), 2) AS min_fee_pkr,
    ROUND(MAX(fee_pkr), 2) AS max_fee_pkr
FROM silver_fact
GROUP BY city
ORDER BY avg_fee_pkr DESC;
""",
    },
    {
        "id": "REV-08",
        "category": "Revenue Analysis",
        "name": "Peak Revenue Hours",
        "description": "Top revenue-generating hours across all locations.",
        "sql": """
SELECT
    CAST(entry_hour AS INTEGER) AS hour_of_day,
    COUNT(*)                    AS transactions,
    ROUND(SUM(fee_pkr), 0)      AS total_revenue_pkr,
    ROUND(AVG(fee_pkr), 2)      AS avg_fee_pkr
FROM silver_fact
GROUP BY entry_hour
ORDER BY total_revenue_pkr DESC
LIMIT 10;
""",
    },
    {
        "id": "REV-09",
        "category": "Revenue Analysis",
        "name": "Revenue: Eid vs Normal Days",
        "description": "Compare total and average revenue on Eid days vs regular days.",
        "sql": """
SELECT
    CASE WHEN is_eid = 1 THEN 'Eid Days' ELSE 'Normal Days' END AS day_type,
    COUNT(DISTINCT entry_date)       AS distinct_days,
    COUNT(*)                         AS transactions,
    ROUND(SUM(fee_pkr), 0)           AS total_revenue_pkr,
    ROUND(AVG(fee_pkr), 2)           AS avg_fee_pkr,
    ROUND(SUM(fee_pkr) / COUNT(DISTINCT entry_date), 0) AS revenue_per_day
FROM silver_fact
GROUP BY day_type
ORDER BY revenue_per_day DESC;
""",
    },
    {
        "id": "REV-10",
        "category": "Revenue Analysis",
        "name": "PKR Fee Distribution Percentiles",
        "description": "Fee distribution: P25, P50, P75, P90, P99 across all transactions.",
        "sql": """
SELECT
    ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY fee_pkr), 0) AS p25,
    ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY fee_pkr), 0) AS p50_median,
    ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY fee_pkr), 0) AS p75,
    ROUND(PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY fee_pkr), 0) AS p90,
    ROUND(PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY fee_pkr), 0) AS p99,
    ROUND(AVG(fee_pkr), 2)    AS mean_fee,
    ROUND(STDDEV(fee_pkr), 2) AS stddev_fee
FROM silver_fact;
""",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # OCCUPANCY & OPERATIONS  (10 queries)
    # ══════════════════════════════════════════════════════════════════════════
    {
        "id": "OPS-01",
        "category": "Occupancy & Operations",
        "name": "Current Occupancy Rate per Location",
        "description": "Estimated occupancy rate per location using hourly utilisation.",
        "sql": """
SELECT
    location_name,
    city,
    zone_type,
    total_slots,
    total_transactions,
    ROUND(daily_utilisation_rate * 100, 2) AS utilisation_pct
FROM gold_location_performance
ORDER BY utilisation_pct DESC;
""",
    },
    {
        "id": "OPS-02",
        "category": "Occupancy & Operations",
        "name": "Hourly Occupancy Heatmap Data",
        "description": "Transaction counts by hour and day-of-week for heatmap visualisation.",
        "sql": """
SELECT
    CAST(entry_hour AS INTEGER)  AS hour,
    CAST(day_of_week AS INTEGER) AS day_of_week,
    COUNT(*)                     AS transaction_count,
    ROUND(AVG(fee_pkr), 2)       AS avg_fee
FROM silver_fact
GROUP BY entry_hour, day_of_week
ORDER BY day_of_week, hour;
""",
    },
    {
        "id": "OPS-03",
        "category": "Occupancy & Operations",
        "name": "Average Duration by Vehicle Type",
        "description": "Understand how long different vehicle types park on average.",
        "sql": """
SELECT
    vehicle_type,
    COUNT(*)                        AS transactions,
    ROUND(AVG(duration_minutes), 1) AS avg_duration_min,
    ROUND(MIN(duration_minutes), 0) AS min_duration_min,
    ROUND(MAX(duration_minutes), 0) AS max_duration_min
FROM silver_fact
GROUP BY vehicle_type
ORDER BY avg_duration_min DESC;
""",
    },
    {
        "id": "OPS-04",
        "category": "Occupancy & Operations",
        "name": "Busiest Day of Week per City",
        "description": "Identify which weekday drives the most transactions per city.",
        "sql": """
SELECT
    city,
    CAST(day_of_week AS INTEGER) AS day_of_week,
    CASE CAST(day_of_week AS INTEGER)
        WHEN 0 THEN 'Monday'   WHEN 1 THEN 'Tuesday'
        WHEN 2 THEN 'Wednesday' WHEN 3 THEN 'Thursday'
        WHEN 4 THEN 'Friday'   WHEN 5 THEN 'Saturday'
        WHEN 6 THEN 'Sunday'   ELSE 'Unknown'
    END AS day_name,
    COUNT(*) AS transactions
FROM silver_fact
GROUP BY city, day_of_week
QUALIFY ROW_NUMBER() OVER (PARTITION BY city ORDER BY COUNT(*) DESC) = 1
ORDER BY city;
""",
    },
    {
        "id": "OPS-05",
        "category": "Occupancy & Operations",
        "name": "Slot Utilisation Rate",
        "description": "Ratio of transactions to total capacity across locations.",
        "sql": """
SELECT
    location_id,
    location_name,
    city,
    total_slots,
    total_transactions,
    ROUND(daily_utilisation_rate * 100, 2) AS daily_utilisation_pct,
    CASE
        WHEN daily_utilisation_rate > 0.8 THEN 'High'
        WHEN daily_utilisation_rate > 0.5 THEN 'Medium'
        ELSE 'Low'
    END AS utilisation_band
FROM gold_location_performance
ORDER BY daily_utilisation_rate DESC;
""",
    },
    {
        "id": "OPS-06",
        "category": "Occupancy & Operations",
        "name": "Longest Average Parking Duration by Location",
        "description": "Which locations see customers park the longest?",
        "sql": """
SELECT
    location_name,
    city,
    zone_type,
    ROUND(avg_duration_minutes, 1) AS avg_duration_min,
    total_transactions
FROM gold_location_performance
ORDER BY avg_duration_minutes DESC
LIMIT 15;
""",
    },
    {
        "id": "OPS-07",
        "category": "Occupancy & Operations",
        "name": "Jummah vs Weekday Occupancy",
        "description": "Compare transaction volumes on Fridays (Jummah) vs other weekdays.",
        "sql": """
SELECT
    CASE WHEN day_of_week = 4 THEN 'Friday (Jummah)'
         ELSE 'Other Weekdays' END AS day_type,
    COUNT(*)                   AS transactions,
    ROUND(AVG(fee_pkr), 2)     AS avg_fee_pkr,
    ROUND(AVG(duration_minutes), 1) AS avg_duration_min
FROM silver_fact
WHERE day_of_week BETWEEN 0 AND 4
GROUP BY day_type
ORDER BY transactions DESC;
""",
    },
    {
        "id": "OPS-08",
        "category": "Occupancy & Operations",
        "name": "Monsoon Season Occupancy Impact",
        "description": "Compare transaction volumes in monsoon months (Jul-Sep) vs rest of year.",
        "sql": """
SELECT
    CASE WHEN is_monsoon = 1 THEN 'Monsoon (Jul-Sep)'
         ELSE 'Non-Monsoon' END AS season,
    COUNT(DISTINCT entry_date)  AS days,
    COUNT(*)                    AS total_transactions,
    ROUND(COUNT(*) * 1.0 / COUNT(DISTINCT entry_date), 1) AS txn_per_day,
    ROUND(AVG(fee_pkr), 2)      AS avg_fee_pkr
FROM silver_fact
GROUP BY season
ORDER BY txn_per_day DESC;
""",
    },
    {
        "id": "OPS-09",
        "category": "Occupancy & Operations",
        "name": "Slot Turnover Rate per Day",
        "description": "How many times each slot turns over per day on average.",
        "sql": """
SELECT
    location_id,
    location_name,
    city,
    total_slots,
    ROUND(total_transactions * 1.0 /
        NULLIF(total_slots, 0) /
        NULLIF(
            DATE_DIFF('day',
                CAST(first_transaction_date AS DATE),
                CAST(last_transaction_date  AS DATE)
            ), 0
        ), 2) AS turnover_per_slot_per_day
FROM gold_location_performance
ORDER BY turnover_per_slot_per_day DESC
LIMIT 20;
""",
    },
    {
        "id": "OPS-10",
        "category": "Occupancy & Operations",
        "name": "Locations Below 50% Utilisation",
        "description": "Identify underperforming locations for management action.",
        "sql": """
SELECT
    location_name,
    city,
    province,
    zone_type,
    total_slots,
    total_transactions,
    ROUND(daily_utilisation_rate * 100, 2) AS utilisation_pct
FROM gold_location_performance
WHERE daily_utilisation_rate < 0.5
ORDER BY utilisation_pct ASC;
""",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # CUSTOMER ANALYTICS  (10 queries)
    # ══════════════════════════════════════════════════════════════════════════
    {
        "id": "CUST-01",
        "category": "Customer Analytics",
        "name": "Top 20 Customers by Spend",
        "description": "Highest-value customers ranked by lifetime spend.",
        "sql": """
SELECT
    customer_id,
    full_name,
    customer_city,
    frequency                   AS total_visits,
    ROUND(monetary_pkr, 0)      AS lifetime_spend_pkr,
    ROUND(avg_spend_pkr, 2)     AS avg_spend_pkr,
    recency_days,
    has_season_pass
FROM gold_customer_rfm
ORDER BY monetary_pkr DESC
LIMIT 20;
""",
    },
    {
        "id": "CUST-02",
        "category": "Customer Analytics",
        "name": "Season Pass vs Casual Ratio",
        "description": "How many customers have season passes vs casual one-time users?",
        "sql": """
SELECT
    has_season_pass,
    COUNT(*)                    AS customer_count,
    ROUND(AVG(monetary_pkr), 0) AS avg_lifetime_spend,
    ROUND(AVG(frequency), 1)    AS avg_visits,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct
FROM gold_customer_rfm
GROUP BY has_season_pass
ORDER BY has_season_pass DESC;
""",
    },
    {
        "id": "CUST-03",
        "category": "Customer Analytics",
        "name": "Customer Retention Rate (Repeat Visits)",
        "description": "Percentage of customers with more than 1 visit.",
        "sql": """
SELECT
    CASE WHEN frequency = 1 THEN 'One-time'
         WHEN frequency <= 5 THEN '2-5 visits'
         WHEN frequency <= 20 THEN '6-20 visits'
         ELSE '20+ visits' END AS visit_band,
    COUNT(*) AS customers,
    ROUND(AVG(monetary_pkr), 0) AS avg_spend_pkr
FROM gold_customer_rfm
GROUP BY visit_band
ORDER BY MIN(frequency);
""",
    },
    {
        "id": "CUST-04",
        "category": "Customer Analytics",
        "name": "Average Visits per Customer per Month",
        "description": "Monthly visit frequency distribution across all customers.",
        "sql": """
SELECT
    city,
    CAST(entry_month AS INTEGER) AS month,
    COUNT(DISTINCT customer_id)  AS active_customers,
    COUNT(*)                     AS total_visits,
    ROUND(COUNT(*) * 1.0 / COUNT(DISTINCT customer_id), 2) AS visits_per_customer
FROM silver_fact
WHERE customer_id IS NOT NULL
GROUP BY city, entry_month
ORDER BY city, month;
""",
    },
    {
        "id": "CUST-05",
        "category": "Customer Analytics",
        "name": "Customers with Most Violations",
        "description": "Top offenders linked to parking violations.",
        "sql": """
SELECT
    v.vehicle_id,
    COUNT(*)            AS violation_count,
    SUM(v.fine_pkr)     AS total_fines_pkr,
    SUM(CASE WHEN v.fine_paid THEN 1 ELSE 0 END) AS fines_paid
FROM silver_violations v
GROUP BY v.vehicle_id
ORDER BY violation_count DESC
LIMIT 20;
""",
    },
    {
        "id": "CUST-06",
        "category": "Customer Analytics",
        "name": "RFM Segmentation",
        "description": "Customers segmented by Recency, Frequency, Monetary quintile scores.",
        "sql": """
SELECT
    customer_id,
    full_name,
    recency_days,
    frequency,
    ROUND(monetary_pkr, 0) AS monetary_pkr,
    NTILE(5) OVER (ORDER BY recency_days ASC)  AS r_score,
    NTILE(5) OVER (ORDER BY frequency DESC)    AS f_score,
    NTILE(5) OVER (ORDER BY monetary_pkr DESC) AS m_score
FROM gold_customer_rfm
ORDER BY m_score DESC, f_score DESC, r_score DESC
LIMIT 100;
""",
    },
    {
        "id": "CUST-07",
        "category": "Customer Analytics",
        "name": "New vs Returning Customers by Month",
        "description": "Monthly split of first-time vs repeat customer visits.",
        "sql": """
WITH first_visits AS (
    SELECT customer_id, MIN(entry_date) AS first_visit
    FROM silver_fact
    WHERE customer_id IS NOT NULL
    GROUP BY customer_id
)
SELECT
    DATE_TRUNC('month', f.entry_date) AS month,
    COUNT(CASE WHEN f.entry_date = fv.first_visit THEN 1 END) AS new_customers,
    COUNT(CASE WHEN f.entry_date > fv.first_visit  THEN 1 END) AS returning_visits
FROM silver_fact f
JOIN first_visits fv ON f.customer_id = fv.customer_id
WHERE f.customer_id IS NOT NULL
GROUP BY DATE_TRUNC('month', f.entry_date)
ORDER BY month;
""",
    },
    {
        "id": "CUST-08",
        "category": "Customer Analytics",
        "name": "Customers by City",
        "description": "Customer distribution across Pakistani cities.",
        "sql": """
SELECT
    customer_city,
    COUNT(*)                    AS customers,
    ROUND(AVG(monetary_pkr), 0) AS avg_lifetime_spend,
    ROUND(AVG(frequency), 1)    AS avg_visits,
    SUM(CASE WHEN has_season_pass THEN 1 ELSE 0 END) AS season_pass_holders
FROM gold_customer_rfm
GROUP BY customer_city
ORDER BY customers DESC;
""",
    },
    {
        "id": "CUST-09",
        "category": "Customer Analytics",
        "name": "Average Fee per Customer Segment",
        "description": "Spending behaviour comparison across customer types.",
        "sql": """
SELECT
    CASE
        WHEN has_season_pass THEN 'Season Pass Holder'
        WHEN frequency > 20  THEN 'High Frequency'
        WHEN frequency > 5   THEN 'Regular'
        ELSE 'Casual'
    END AS segment,
    COUNT(*)                    AS customers,
    ROUND(AVG(avg_spend_pkr), 2) AS avg_fee_pkr,
    ROUND(AVG(frequency), 1)    AS avg_visits
FROM gold_customer_rfm
GROUP BY segment
ORDER BY avg_fee_pkr DESC;
""",
    },
    {
        "id": "CUST-10",
        "category": "Customer Analytics",
        "name": "Churn Risk Customers (60+ Days Inactive)",
        "description": "Customers who have not visited in 60+ days — churn risk.",
        "sql": """
SELECT
    customer_id,
    full_name,
    customer_city,
    recency_days,
    frequency,
    ROUND(monetary_pkr, 0) AS lifetime_spend_pkr,
    has_season_pass
FROM gold_customer_rfm
WHERE recency_days > 60
ORDER BY monetary_pkr DESC
LIMIT 50;
""",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # VIOLATIONS & ANOMALIES  (8 queries)
    # ══════════════════════════════════════════════════════════════════════════
    {
        "id": "VIOL-01",
        "category": "Violations & Anomalies",
        "name": "Total Violations by Type",
        "description": "Count and revenue impact of each violation category.",
        "sql": """
SELECT
    violation_type,
    COUNT(*)              AS violation_count,
    ROUND(SUM(fine_pkr), 0) AS total_fines_pkr,
    ROUND(AVG(fine_pkr), 0) AS avg_fine_pkr,
    SUM(CASE WHEN fine_paid THEN 1 ELSE 0 END) AS paid_count,
    ROUND(100.0 * SUM(CASE WHEN fine_paid THEN 1 ELSE 0 END) / COUNT(*), 1) AS paid_pct
FROM silver_violations
GROUP BY violation_type
ORDER BY violation_count DESC;
""",
    },
    {
        "id": "VIOL-02",
        "category": "Violations & Anomalies",
        "name": "Violation Hotspots by Location",
        "description": "Which parking locations have the most violations?",
        "sql": """
SELECT
    v.location_id,
    l.location_name,
    l.city,
    l.zone_type,
    COUNT(*)              AS violation_count,
    ROUND(SUM(v.fine_pkr), 0) AS total_fines_pkr
FROM silver_violations v
JOIN silver_locations l ON v.location_id = l.location_id
GROUP BY v.location_id, l.location_name, l.city, l.zone_type
ORDER BY violation_count DESC
LIMIT 15;
""",
    },
    {
        "id": "VIOL-03",
        "category": "Violations & Anomalies",
        "name": "Repeat Offenders (3+ Violations)",
        "description": "Vehicles appearing in the violations table 3 or more times.",
        "sql": """
SELECT
    vehicle_id,
    COUNT(*)              AS violation_count,
    ROUND(SUM(fine_pkr), 0) AS total_fines_pkr,
    COUNT(DISTINCT violation_type) AS distinct_violation_types,
    MIN(violation_time) AS first_violation,
    MAX(violation_time) AS last_violation
FROM silver_violations
GROUP BY vehicle_id
HAVING COUNT(*) >= 3
ORDER BY violation_count DESC
LIMIT 25;
""",
    },
    {
        "id": "VIOL-04",
        "category": "Violations & Anomalies",
        "name": "Off-Hours Access Anomalies",
        "description": "Transactions entering between midnight and 5am — potential anomalies.",
        "sql": """
SELECT
    transaction_id,
    location_id,
    city,
    vehicle_type,
    entry_time,
    entry_hour,
    duration_minutes,
    fee_pkr
FROM silver_fact
WHERE entry_hour BETWEEN 0 AND 4
ORDER BY entry_time DESC
LIMIT 100;
""",
    },
    {
        "id": "VIOL-05",
        "category": "Violations & Anomalies",
        "name": "Blacklisted Plates Detected",
        "description": "All transactions involving vehicles flagged as blacklisted.",
        "sql": """
SELECT
    f.transaction_id,
    f.plate_number,
    f.vehicle_type,
    f.location_id,
    f.city,
    f.entry_time,
    f.fee_pkr
FROM silver_fact f
WHERE f.is_blacklisted = TRUE
ORDER BY f.entry_time DESC
LIMIT 50;
""",
    },
    {
        "id": "VIOL-06",
        "category": "Violations & Anomalies",
        "name": "Violation Revenue (Fines Collected)",
        "description": "Total fine revenue collected vs outstanding across all locations.",
        "sql": """
SELECT
    ROUND(SUM(fine_pkr), 0) AS total_fines_issued_pkr,
    ROUND(SUM(CASE WHEN fine_paid THEN fine_pkr ELSE 0 END), 0) AS fines_collected_pkr,
    ROUND(SUM(CASE WHEN NOT fine_paid THEN fine_pkr ELSE 0 END), 0) AS outstanding_pkr,
    ROUND(100.0 * SUM(CASE WHEN fine_paid THEN 1 ELSE 0 END) / COUNT(*), 1) AS collection_rate_pct
FROM silver_violations;
""",
    },
    {
        "id": "VIOL-07",
        "category": "Violations & Anomalies",
        "name": "Overstay Rate by Location",
        "description": "Percentage of transactions flagged as Overstay per location.",
        "sql": """
SELECT
    v.location_id,
    l.location_name,
    l.city,
    COUNT(*)                               AS total_violations,
    SUM(CASE WHEN v.violation_type = 'Overstay' THEN 1 ELSE 0 END) AS overstay_count,
    ROUND(100.0 * SUM(CASE WHEN v.violation_type = 'Overstay' THEN 1 ELSE 0 END)
          / COUNT(*), 2) AS overstay_pct
FROM silver_violations v
JOIN silver_locations l ON v.location_id = l.location_id
GROUP BY v.location_id, l.location_name, l.city
HAVING COUNT(*) >= 5
ORDER BY overstay_pct DESC
LIMIT 20;
""",
    },
    {
        "id": "VIOL-08",
        "category": "Violations & Anomalies",
        "name": "Anomaly-Flagged Transactions by Hour",
        "description": "Distribution of ML-flagged anomalous transactions across hours of day.",
        "sql": """
SELECT
    entry_hour,
    COUNT(*)                    AS total_transactions,
    SUM(is_anomaly)             AS anomaly_count,
    ROUND(100.0 * AVG(is_anomaly), 2) AS anomaly_rate_pct
FROM silver_fact
WHERE is_anomaly IS NOT NULL
GROUP BY entry_hour
ORDER BY entry_hour;
""",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ANPR & SENSOR EVENTS  (7 queries)
    # ══════════════════════════════════════════════════════════════════════════
    {
        "id": "ANPR-01",
        "category": "ANPR & Sensor Events",
        "name": "ANPR Scan Accuracy by Camera",
        "description": "Average confidence score per camera — identify underperforming cameras.",
        "sql": """
SELECT
    camera_id,
    location_id,
    COUNT(*)                          AS total_scans,
    ROUND(AVG(confidence_score), 4)   AS avg_confidence,
    ROUND(MIN(confidence_score), 4)   AS min_confidence,
    SUM(CASE WHEN is_blacklisted_hit THEN 1 ELSE 0 END) AS blacklist_hits
FROM silver_anpr
GROUP BY camera_id, location_id
ORDER BY avg_confidence ASC
LIMIT 20;
""",
    },
    {
        "id": "ANPR-02",
        "category": "ANPR & Sensor Events",
        "name": "Plates Scanned per Location per Day",
        "description": "Daily ANPR activity volume per parking location.",
        "sql": """
SELECT
    location_id,
    CAST(scan_time AS DATE)    AS scan_date,
    COUNT(*)                   AS total_scans,
    COUNT(DISTINCT vehicle_id) AS unique_vehicles
FROM silver_anpr
GROUP BY location_id, CAST(scan_time AS DATE)
ORDER BY total_scans DESC
LIMIT 30;
""",
    },
    {
        "id": "ANPR-03",
        "category": "ANPR & Sensor Events",
        "name": "ANPR Confidence Score Distribution",
        "description": "Distribution of scan confidence scores across all cameras.",
        "sql": """
SELECT
    CASE
        WHEN confidence_score >= 0.95 THEN '0.95-1.00 (Excellent)'
        WHEN confidence_score >= 0.85 THEN '0.85-0.95 (Good)'
        WHEN confidence_score >= 0.75 THEN '0.75-0.85 (Fair)'
        ELSE 'Below 0.75 (Poor)'
    END AS confidence_band,
    COUNT(*) AS scan_count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct
FROM silver_anpr
GROUP BY confidence_band
ORDER BY MIN(confidence_score) DESC;
""",
    },
    {
        "id": "ANPR-04",
        "category": "ANPR & Sensor Events",
        "name": "Sensor Uptime Rate",
        "description": "How often sensors report vs expected heartbeat frequency.",
        "sql": """
SELECT
    location_id,
    COUNT(DISTINCT slot_id)    AS monitored_slots,
    COUNT(*)                   AS total_pings,
    ROUND(COUNT(*) * 1.0 / COUNT(DISTINCT slot_id), 1) AS pings_per_slot
FROM sensor_events
GROUP BY location_id
ORDER BY pings_per_slot DESC;
""",
    },
    {
        "id": "ANPR-05",
        "category": "ANPR & Sensor Events",
        "name": "Average Sensor Pings per Occupied Slot",
        "description": "Sensor heartbeat density for occupied slots.",
        "sql": """
SELECT
    location_id,
    status,
    COUNT(DISTINCT slot_id)    AS slots,
    COUNT(*)                   AS total_pings,
    ROUND(COUNT(*) * 1.0 / COUNT(DISTINCT slot_id), 2) AS avg_pings_per_slot
FROM sensor_events
GROUP BY location_id, status
ORDER BY location_id, status;
""",
    },
    {
        "id": "ANPR-06",
        "category": "ANPR & Sensor Events",
        "name": "Mismatched ANPR vs Transaction Events",
        "description": "ANPR scans with no matching transaction — potential gate jump or error.",
        "sql": """
SELECT
    COUNT(*) AS total_anpr_scans,
    SUM(CASE WHEN transaction_id IS NULL THEN 1 ELSE 0 END) AS no_transaction_match,
    ROUND(100.0 * SUM(CASE WHEN transaction_id IS NULL THEN 1 ELSE 0 END)
          / COUNT(*), 2) AS mismatch_rate_pct
FROM silver_anpr;
""",
    },
    {
        "id": "ANPR-07",
        "category": "ANPR & Sensor Events",
        "name": "Top 10 Most Scanned Plates",
        "description": "Vehicles with the highest ANPR scan frequency.",
        "sql": """
SELECT
    vehicle_id,
    plate_number,
    COUNT(*) AS scan_count,
    ROUND(AVG(confidence_score), 4) AS avg_confidence,
    SUM(CASE WHEN is_blacklisted_hit THEN 1 ELSE 0 END) AS blacklist_hits
FROM silver_anpr
WHERE vehicle_id IS NOT NULL
GROUP BY vehicle_id, plate_number
ORDER BY scan_count DESC
LIMIT 10;
""",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # STAFF & OPERATIONS  (5 queries)
    # ══════════════════════════════════════════════════════════════════════════
    {
        "id": "STAFF-01",
        "category": "Staff & Operations",
        "name": "Staff Shift Coverage per Location",
        "description": "Total scheduled staff hours per location.",
        "sql": """
SELECT
    location_id,
    COUNT(DISTINCT staff_name)    AS unique_staff,
    COUNT(*)                      AS total_shifts,
    COUNT(DISTINCT role)          AS roles_covered,
    COUNT(DISTINCT shift_type)    AS shift_types
FROM silver_staff
GROUP BY location_id
ORDER BY total_shifts DESC
LIMIT 20;
""",
    },
    {
        "id": "STAFF-02",
        "category": "Staff & Operations",
        "name": "Cashier Transaction Counts per Shift",
        "description": "Estimated transaction throughput per shift type.",
        "sql": """
SELECT
    s.shift_type,
    COUNT(DISTINCT s.shift_id)   AS total_shifts,
    COUNT(DISTINCT s.staff_name) AS cashiers
FROM silver_staff s
WHERE s.role = 'Cashier'
GROUP BY s.shift_type
ORDER BY cashiers DESC;
""",
    },
    {
        "id": "STAFF-03",
        "category": "Staff & Operations",
        "name": "Peak Understaffed Hours",
        "description": "Hours with high transaction volume but potentially low staff (Night shifts).",
        "sql": """
SELECT
    entry_hour,
    COUNT(*) AS transactions,
    CASE
        WHEN entry_hour BETWEEN 22 AND 23 OR entry_hour BETWEEN 0 AND 5
        THEN 'Night Shift (Understaffed Risk)'
        WHEN entry_hour BETWEEN 6 AND 13
        THEN 'Morning Shift'
        ELSE 'Evening Shift'
    END AS shift_window
FROM silver_fact
GROUP BY entry_hour
ORDER BY entry_hour;
""",
    },
    {
        "id": "STAFF-04",
        "category": "Staff & Operations",
        "name": "Valet Requests by Location",
        "description": "Locations with valet service and their transaction volume.",
        "sql": """
SELECT
    l.location_id,
    l.location_name,
    l.city,
    l.has_valet,
    COUNT(f.transaction_id) AS transactions,
    ROUND(SUM(f.fee_pkr), 0) AS total_revenue_pkr
FROM silver_locations l
LEFT JOIN silver_fact f ON l.location_id = f.location_id
WHERE l.has_valet = TRUE
GROUP BY l.location_id, l.location_name, l.city, l.has_valet
ORDER BY transactions DESC;
""",
    },
    {
        "id": "STAFF-05",
        "category": "Staff & Operations",
        "name": "Guard-to-Slot Ratio",
        "description": "Security guard coverage relative to parking capacity.",
        "sql": """
SELECT
    s.location_id,
    l.location_name,
    l.city,
    l.total_slots,
    COUNT(CASE WHEN s.role = 'Security Guard' THEN 1 END) AS guard_shifts,
    ROUND(
        l.total_slots * 1.0 /
        NULLIF(COUNT(CASE WHEN s.role = 'Security Guard' THEN 1 END), 0),
        1
    ) AS slots_per_guard_shift
FROM silver_staff s
JOIN silver_locations l ON s.location_id = l.location_id
GROUP BY s.location_id, l.location_name, l.city, l.total_slots
ORDER BY slots_per_guard_shift DESC
LIMIT 20;
""",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # BONUS QUERIES  (additional 10 queries to exceed 50 total)
    # ══════════════════════════════════════════════════════════════════════════
    {
        "id": "BONUS-01",
        "category": "Bonus Analytics",
        "name": "Ramadan Revenue Pattern",
        "description": "Hourly revenue breakdown during Ramadan vs non-Ramadan periods.",
        "sql": """
SELECT
    CAST(entry_hour AS INTEGER) AS hour,
    SUM(CASE WHEN is_ramadan = 1 THEN fee_pkr ELSE 0 END)   AS ramadan_revenue,
    SUM(CASE WHEN is_ramadan = 0 THEN fee_pkr ELSE 0 END)   AS normal_revenue,
    COUNT(CASE WHEN is_ramadan = 1 THEN 1 END)              AS ramadan_txns,
    COUNT(CASE WHEN is_ramadan = 0 THEN 1 END)              AS normal_txns
FROM silver_fact
GROUP BY entry_hour
ORDER BY hour;
""",
    },
    {
        "id": "BONUS-02",
        "category": "Bonus Analytics",
        "name": "Revenue per Province",
        "description": "Provincial revenue breakdown across Punjab, Sindh, KPK, etc.",
        "sql": """
SELECT
    province,
    COUNT(DISTINCT city)          AS cities,
    COUNT(DISTINCT location_id)   AS locations,
    COUNT(*)                      AS transactions,
    ROUND(SUM(fee_pkr), 0)        AS total_revenue_pkr,
    ROUND(AVG(fee_pkr), 2)        AS avg_fee_pkr
FROM silver_fact
GROUP BY province
ORDER BY total_revenue_pkr DESC;
""",
    },
    {
        "id": "BONUS-03",
        "category": "Bonus Analytics",
        "name": "EV Charging Location Revenue",
        "description": "Revenue from locations with EV charging infrastructure.",
        "sql": """
SELECT
    l.location_name,
    l.city,
    l.has_ev_charging,
    COUNT(f.transaction_id) AS transactions,
    ROUND(SUM(f.fee_pkr), 0) AS total_revenue_pkr,
    ROUND(AVG(f.fee_pkr), 2) AS avg_fee_pkr
FROM silver_locations l
LEFT JOIN silver_fact f ON l.location_id = f.location_id
WHERE l.has_ev_charging = TRUE
GROUP BY l.location_name, l.city, l.has_ev_charging
ORDER BY total_revenue_pkr DESC;
""",
    },
    {
        "id": "BONUS-04",
        "category": "Bonus Analytics",
        "name": "Zone Type Performance Comparison",
        "description": "KPIs across all parking zone types (Commercial, Hospital, Market etc.).",
        "sql": """
SELECT
    zone_type,
    COUNT(DISTINCT location_id)   AS locations,
    COUNT(*)                      AS transactions,
    ROUND(AVG(fee_pkr), 2)        AS avg_fee_pkr,
    ROUND(AVG(duration_minutes), 1) AS avg_duration_min,
    ROUND(SUM(fee_pkr), 0)        AS total_revenue_pkr
FROM silver_fact
GROUP BY zone_type
ORDER BY total_revenue_pkr DESC;
""",
    },
    {
        "id": "BONUS-05",
        "category": "Bonus Analytics",
        "name": "Year-over-Year Revenue Comparison",
        "description": "Compare 2023 vs 2024 revenue by city.",
        "sql": """
SELECT
    city,
    SUM(CASE WHEN entry_year = 2023 THEN fee_pkr ELSE 0 END) AS revenue_2023,
    SUM(CASE WHEN entry_year = 2024 THEN fee_pkr ELSE 0 END) AS revenue_2024,
    ROUND(
        (SUM(CASE WHEN entry_year = 2024 THEN fee_pkr ELSE 0 END)
        - SUM(CASE WHEN entry_year = 2023 THEN fee_pkr ELSE 0 END))
        / NULLIF(SUM(CASE WHEN entry_year = 2023 THEN fee_pkr ELSE 0 END), 0) * 100,
        2
    ) AS yoy_growth_pct
FROM silver_fact
GROUP BY city
ORDER BY yoy_growth_pct DESC;
""",
    },
    {
        "id": "BONUS-06",
        "category": "Bonus Analytics",
        "name": "Covered vs Open Parking Revenue",
        "description": "Revenue split between covered and open-air parking facilities.",
        "sql": """
SELECT
    l.is_covered,
    CASE WHEN l.is_covered THEN 'Covered' ELSE 'Open Air' END AS parking_type,
    COUNT(DISTINCT l.location_id) AS locations,
    COUNT(f.transaction_id) AS transactions,
    ROUND(AVG(f.fee_pkr), 2) AS avg_fee_pkr,
    ROUND(SUM(f.fee_pkr), 0) AS total_revenue_pkr
FROM silver_locations l
LEFT JOIN silver_fact f ON l.location_id = f.location_id
GROUP BY l.is_covered
ORDER BY total_revenue_pkr DESC;
""",
    },
    {
        "id": "BONUS-07",
        "category": "Bonus Analytics",
        "name": "Customer Age Group Analysis",
        "description": "Spending patterns segmented by age bracket.",
        "sql": """
SELECT
    CASE
        WHEN age < 25 THEN 'Under 25'
        WHEN age < 35 THEN '25-34'
        WHEN age < 45 THEN '35-44'
        WHEN age < 55 THEN '45-54'
        ELSE '55+'
    END AS age_group,
    COUNT(*)                    AS customers,
    ROUND(AVG(monetary_pkr), 0) AS avg_lifetime_spend,
    ROUND(AVG(frequency), 1)    AS avg_visits
FROM gold_customer_rfm
GROUP BY age_group
ORDER BY MIN(age);
""",
    },
    {
        "id": "BONUS-08",
        "category": "Bonus Analytics",
        "name": "Independence Day Parking Surge",
        "description": "Transactions and revenue on Independence Day (Aug 14) vs normal August days.",
        "sql": """
SELECT
    CASE WHEN is_independence_day = 1 THEN 'Independence Day (Aug 14)'
         ELSE 'Other August Days' END AS day_type,
    COUNT(DISTINCT entry_date) AS days,
    COUNT(*)                   AS transactions,
    ROUND(SUM(fee_pkr), 0)     AS total_revenue_pkr,
    ROUND(AVG(fee_pkr), 2)     AS avg_fee_pkr
FROM silver_fact
WHERE entry_month = 8
GROUP BY day_type
ORDER BY avg_fee_pkr DESC;
""",
    },
    {
        "id": "BONUS-09",
        "category": "Bonus Analytics",
        "name": "Medallion Layer Summary",
        "description": "Row counts across all Medallion layers from the data catalog.",
        "sql": """
SELECT
    layer,
    COUNT(*)          AS dataset_count,
    SUM(row_count)    AS total_rows
FROM catalog_view
GROUP BY layer
ORDER BY
    CASE layer
        WHEN 'Bronze'   THEN 1
        WHEN 'Silver'   THEN 2
        WHEN 'Gold'     THEN 3
        WHEN 'Platinum' THEN 4
        ELSE 5
    END;
""",
    },
    {
        "id": "BONUS-10",
        "category": "Bonus Analytics",
        "name": "Full Pipeline Data Flow Summary",
        "description": "End-to-end transaction count at each Medallion layer.",
        "sql": """
SELECT 'Bronze (raw)'        AS layer, COUNT(*) AS row_count FROM bronze_transactions
UNION ALL
SELECT 'Silver (cleaned)'    AS layer, COUNT(*) AS row_count FROM silver_fact
UNION ALL
SELECT 'Gold (daily_rev)'    AS layer, COUNT(*) AS row_count FROM gold_daily_revenue
ORDER BY row_count DESC;
""",
    },
]


def get_categories() -> list:
    """Return unique categories in order."""
    seen = []
    for q in QUERY_LIBRARY:
        if q["category"] not in seen:
            seen.append(q["category"])
    return seen


def get_by_category(category: str) -> list:
    return [q for q in QUERY_LIBRARY if q["category"] == category]


def get_by_id(qid: str) -> dict:
    for q in QUERY_LIBRARY:
        if q["id"] == qid:
            return q
    return {}

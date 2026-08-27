
-- Drop the table to allow for clean re-runs
DROP TABLE IF EXISTS training_features;

-- Create the master feature table for ML training
CREATE TABLE training_features AS

WITH TimeGaps AS (
    SELECT 
        *,
        -- GAP: Time since the customer's last swipe in minutes
        EXTRACT(EPOCH FROM (
            transaction_date - LAG(transaction_date) OVER (
                PARTITION BY customer_id 
                ORDER BY transaction_date
            )
        )) / 60.0 AS minutes_since_last_txn
    FROM transactions
),
RunningStats AS (
    SELECT 
        *,
        -- RUNNING AVERAGE & STD DEV (strictly excluding current txn)
        AVG(amount) OVER (PARTITION BY customer_id ORDER BY transaction_date ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS hist_avg_amount,
        STDDEV(amount) OVER (PARTITION BY customer_id ORDER BY transaction_date ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS hist_stddev_amount,
        
        -- VELOCITY (Rolling 30-minute window)
        COUNT(id) OVER (PARTITION BY customer_id ORDER BY transaction_date RANGE BETWEEN INTERVAL '30 minutes' PRECEDING AND CURRENT ROW) AS txn_count_30m,
        SUM(amount) OVER (PARTITION BY customer_id ORDER BY transaction_date RANGE BETWEEN INTERVAL '30 minutes' PRECEDING AND CURRENT ROW) AS total_amount_30m,

        -- PROFILES FEATURES : 
		-- P7D (7-day profile), INCLUDING current row first
        COUNT(*) OVER (
            PARTITION BY customer_id ORDER BY transaction_date
            RANGE BETWEEN INTERVAL '7 days' PRECEDING AND CURRENT ROW
        ) AS p7d_count_incl,
        SUM(amount) OVER (
            PARTITION BY customer_id ORDER BY transaction_date
            RANGE BETWEEN INTERVAL '7 days' PRECEDING AND CURRENT ROW
        ) AS p7d_sum_incl,
        STDDEV(amount) OVER (
            PARTITION BY customer_id ORDER BY transaction_date
            RANGE BETWEEN INTERVAL '7 days' PRECEDING AND CURRENT ROW
        ) AS p7d_std_incl,

        -- P30D
        COUNT(*) OVER (
            PARTITION BY customer_id ORDER BY transaction_date
            RANGE BETWEEN INTERVAL '30 days' PRECEDING AND CURRENT ROW
        ) AS p30d_count_incl,
        SUM(amount) OVER (
            PARTITION BY customer_id ORDER BY transaction_date
            RANGE BETWEEN INTERVAL '30 days' PRECEDING AND CURRENT ROW
        ) AS p30d_sum_incl,
        STDDEV(amount) OVER (
            PARTITION BY customer_id ORDER BY transaction_date
            RANGE BETWEEN INTERVAL '30 days' PRECEDING AND CURRENT ROW
        ) AS p30d_std_incl,

        -- P90D
        COUNT(*) OVER (
            PARTITION BY customer_id ORDER BY transaction_date
            RANGE BETWEEN INTERVAL '90 days' PRECEDING AND CURRENT ROW
        ) AS p90d_count_incl,
        SUM(amount) OVER (
            PARTITION BY customer_id ORDER BY transaction_date
            RANGE BETWEEN INTERVAL '90 days' PRECEDING AND CURRENT ROW
        ) AS p90d_sum_incl,
        STDDEV(amount) OVER (
            PARTITION BY customer_id ORDER BY transaction_date
            RANGE BETWEEN INTERVAL '90 days' PRECEDING AND CURRENT ROW
        ) AS p90d_std_incl,
        
        -- GAP VOLATILITY (Burstiness)
        STDDEV(minutes_since_last_txn) OVER (PARTITION BY customer_id ORDER BY transaction_date ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING) AS gap_volatility_5tx
        
    FROM TimeGaps
)
SELECT 
    r.id AS transaction_id,
    r.customer_id,
    r.transaction_date,
    r.amount,
    r.merchant_category,
    r.is_active_vpn,
    r.is_international,
    
    COALESCE(r.minutes_since_last_txn, 99999.0) AS minutes_since_last_txn_clean,
    r.txn_count_30m,
    r.total_amount_30m,
    COALESCE(r.gap_volatility_5tx, 0.0) AS gap_volatility_5tx_clean,
    
    CASE 
    WHEN r.hist_stddev_amount IS NULL 
         OR r.hist_stddev_amount = 0 
         OR (COUNT(*) OVER (
                PARTITION BY r.customer_id ORDER BY r.transaction_date
                ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
            )) < 5
    THEN 0.0
    ELSE (r.amount - r.hist_avg_amount) / r.hist_stddev_amount
END AS amount_z_score,
    
    -- MERCHANT DIVERSITY
    (
        SELECT COUNT(DISTINCT t2.merchant)
        FROM transactions t2
        WHERE t2.customer_id = r.customer_id
          AND t2.transaction_date >= (r.transaction_date - INTERVAL '7 days')
          AND t2.transaction_date <= r.transaction_date
    ) AS merchant_diversity_7d,

    
    -- 1. Exact hour of the transaction (0-23)
    EXTRACT(HOUR FROM r.transaction_date) AS hour_of_day,
      
    -- 2. Night transaction flag (1 if between Midnight and 5 AM)
    CASE WHEN EXTRACT(HOUR FROM r.transaction_date) < 5 THEN 1 ELSE 0 END AS is_night_txn,
    
    -- 3. High-Risk Category Flag
    CASE WHEN r.merchant_category IN ('Luxury Goods', 'Financial Services', 'Gaming') THEN 1 ELSE 0 END AS is_high_risk_category,


    -- PROFILES FEATURES
	-- P7D final columns
    (r.p7d_count_incl - 1) AS p7d_txn_count,
    CASE WHEN (r.p7d_count_incl - 1) > 0 
        THEN ROUND(((r.p7d_sum_incl - r.amount) / (r.p7d_count_incl - 1))::numeric, 2) 
        ELSE 0 END AS p7d_avg_amount,
    ROUND((r.p7d_sum_incl - r.amount)::numeric, 2) AS p7d_sum_amount,
    COALESCE(ROUND(r.p7d_std_incl::numeric, 2), 0.0) AS p7d_std_amount,

    -- P30D final columns
    (r.p30d_count_incl - 1) AS p30d_txn_count,
    CASE WHEN (r.p30d_count_incl - 1) > 0 
        THEN ROUND(((r.p30d_sum_incl - r.amount) / (r.p30d_count_incl - 1))::numeric, 2) 
        ELSE 0 END AS p30d_avg_amount,
    ROUND((r.p30d_sum_incl - r.amount)::numeric, 2) AS p30d_sum_amount,
    COALESCE(ROUND(r.p30d_std_incl::numeric, 2), 0.0) AS p30d_std_amount,

    -- P90D final columns
    (r.p90d_count_incl - 1) AS p90d_txn_count,
    CASE WHEN (r.p90d_count_incl - 1) > 0 
        THEN ROUND(((r.p90d_sum_incl - r.amount) / (r.p90d_count_incl - 1))::numeric, 2) 
        ELSE 0 END AS p90d_avg_amount,
    ROUND((r.p90d_sum_incl - r.amount)::numeric, 2) AS p90d_sum_amount,
    COALESCE(ROUND(r.p90d_std_incl::numeric, 2), 0.0) AS p90d_std_amount,
        
    -- [TARGET VARIABLE]
    
    r.is_fraud

FROM RunningStats r;




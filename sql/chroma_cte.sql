-- =========================================================================
-- 1. 建立最終的單一真實來源 (SSoT) 數據資產表：機台指標事實表
-- =========================================================================
CREATE TABLE IF NOT EXISTS fct_machine_metrics (
    metric_pk VARCHAR(64) PRIMARY KEY,       -- 冪等性防護雜湊鍵 (Idempotency Key)
    window_timestamp TIMESTAMP NOT NULL,      -- 10:1 降採樣後的分鐘級時間戳記
    machine_id VARCHAR(50),
    test_station VARCHAR(50),
    channel_id VARCHAR(20),
    lot_id VARCHAR(50),
    avg_voltage NUMERIC(8,3),
    max_voltage NUMERIC(8,3),
    avg_current NUMERIC(8,3),
    avg_temperature NUMERIC(5,2),
    total_raw_points INT,
    is_noise_intercepted INT,                 -- 今日該分鐘內自動攔截的偽陽性噪音次次數
    is_true_anomaly_triggered INT,            -- 今日該分鐘內觸發的真實硬體損壞告警次數
    is_fn_suspect_flagged INT,                -- 今日該分鐘內捕捉到的漏報風險潛在次數
    data_pipeline_version VARCHAR(20),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 為高度時序檢索建立索引，優化 Streamlit Dashboard 的讀取速度
CREATE INDEX IF NOT EXISTS idx_fct_machine_ts ON fct_machine_metrics (window_timestamp, machine_id);


-- =========================================================================
-- 2. 核心 ETL 數據精煉管線 (純 SQL 實作 SPC 動態過濾與降採樣)
-- =========================================================================
INSERT INTO fct_machine_metrics (
    metric_pk, window_timestamp, machine_id, test_station, channel_id, lot_id,
    avg_voltage, max_voltage, avg_current, avg_temperature, total_raw_points,
    is_noise_intercepted, is_true_anomaly_triggered, is_fn_suspect_flagged, data_pipeline_version
)
WITH src_cleaned AS (
    -- 【階段一：髒資料清洗】將 Sensor 斷線產生的 -99.0 轉換為 NULL，並將 timestamp 顯式轉為 TIMESTAMP 型態
    SELECT 
        timestamp::TIMESTAMP as timestamp,
        machine_id,
        test_station,
        channel_id,
        lot_id,
        wafer_id_unit_id,
        CASE WHEN voltage = -99.0 THEN NULL ELSE voltage END as voltage,
        CASE WHEN current = -99.0 THEN NULL ELSE current END as current,
        CASE WHEN temperature = -99.0 THEN NULL ELSE temperature END as temperature,
        test_duration_ms
    FROM raw_machine_logs
),
spc_rolling AS (
    -- 【階段二：滑動視窗計算】動態算出過去 10 筆數據的滑動平均值與標準差 (隔離物理飄移)
    SELECT 
        *,
        AVG(voltage) OVER(
            PARTITION BY machine_id, channel_id 
            ORDER BY timestamp 
            ROWS BETWEEN 10 PRECEDING AND CURRENT ROW
        ) as rolling_avg,
        COALESCE(STDDEV(voltage) OVER(
            PARTITION BY machine_id, channel_id 
            ORDER BY timestamp 
            ROWS BETWEEN 10 PRECEDING AND CURRENT ROW
        ), 0.001) as rolling_std
    FROM src_cleaned
),
z_score_calc AS (
    -- 【階段三：Z-Score 計算與時序前後關聯觀測】
    SELECT 
        *,
        CASE 
            WHEN rolling_std = 0 THEN 0 
            ELSE (voltage - rolling_avg) / rolling_std 
        END as z_score,
        LAG(voltage, 1) OVER(PARTITION BY machine_id, channel_id ORDER BY timestamp) as prev_volt,
        LEAD(voltage, 1) OVER(PARTITION BY machine_id, channel_id ORDER BY timestamp) as next_volt
    FROM spc_rolling
),
anomaly_governance AS (
    -- 【階段四：雙軌治理邏輯判斷】判定偽陽性、真異常與潛在漏報
    SELECT 
        *,
        -- 判斷 1: 偽陽性噪音 (環境干擾) -> 超過 3 倍標準差，且前後點皆正常
        CASE 
            WHEN ABS(z_score) > 3.0 AND (voltage > 8.0) AND (prev_volt < 7.0 AND next_volt < 7.0) THEN 1
            ELSE 0
        END as is_noise,
        
        -- 判斷 2: 真實異常 -> 超過 3 倍標準差，且前後點持續處於高電壓危險區
        CASE 
            WHEN ABS(z_score) > 3.0 AND (voltage > 8.0) AND (prev_volt >= 7.0 OR next_volt >= 7.0) THEN 1
            ELSE 0
        END as is_true_anomaly,
        
        -- 判斷 3: 治理 False Negative (漏報防禦區) -> 電壓雖未破極限，但溫度與時間連鎖攀升
        CASE 
            WHEN voltage BETWEEN 6.5 AND 8.0 AND temperature > 55.0 AND test_duration_ms > 300 THEN 1
            ELSE 0
        END as is_suspect
    FROM z_score_calc
),
downsampling_aggregation AS (
    -- 【階段五：10:1 降採樣聚合】🔥 修正核心：將 GROUP BY 的所有維度通通融入 MD5 雜湊鍵中，徹底杜絕主鍵衝突
    SELECT 
        MD5(machine_id || channel_id || COALESCE(test_station, 'NA') || COALESCE(lot_id, 'NA') || DATE_TRUNC('minute', timestamp)::VARCHAR) as metric_pk,
        DATE_TRUNC('minute', timestamp) as window_timestamp,
        machine_id,
        test_station,
        channel_id,
        lot_id,
        ROUND(AVG(CASE WHEN is_noise = 1 THEN NULL ELSE voltage END)::numeric, 3) as avg_voltage,
        MAX(voltage) as max_voltage,
        ROUND(AVG(current)::numeric, 3) as avg_current,
        ROUND(AVG(temperature)::numeric, 2) as avg_temperature,
        COUNT(*) as total_raw_points,
        SUM(is_noise) as is_noise_intercepted,
        SUM(is_true_anomaly) as is_true_anomaly_triggered,
        SUM(is_suspect) as is_fn_suspect_flagged,
        'v1.0.0' as data_pipeline_version
    FROM anomaly_governance
    GROUP BY DATE_TRUNC('minute', timestamp), machine_id, test_station, channel_id, lot_id
)
-- 【階段六：Upsert 冪等性覆蓋】完美達成 SSoT
SELECT * FROM downsampling_aggregation
ON CONFLICT (metric_pk) DO UPDATE SET
    avg_voltage = EXCLUDED.avg_voltage,
    max_voltage = EXCLUDED.max_voltage,
    avg_current = EXCLUDED.avg_current,
    avg_temperature = EXCLUDED.avg_temperature,
    is_noise_intercepted = EXCLUDED.is_noise_intercepted,
    is_true_anomaly_triggered = EXCLUDED.is_true_anomaly_triggered,
    is_fn_suspect_flagged = EXCLUDED.is_fn_suspect_flagged,
    updated_at = CURRENT_TIMESTAMP;
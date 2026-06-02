# SPC / Z-Score / SQL Window Functions 資料治理

## 1. 本階段目標

使用 PostgreSQL SQL Pipeline，將 Day 2 的 `raw_machine_logs` 轉換成可分析、可查詢、可視覺化的 SSoT Fact Table：

```text
fct_machine_metrics
```

本階段會完成：

* Sensor Disconnect 清洗
* Rolling Average
* Rolling Standard Deviation
* Z-Score
* False Positive Noise 判斷
* True Anomaly 判斷
* False Negative Suspect 判斷
* Downsampling
* Idempotent Upsert
* SSoT Fact Table 建立

---

## 2. 為什麼不用固定閾值？

傳統做法可能會寫：

```sql
WHERE voltage > 8
```

這種方式很直覺，但在工業時間序列資料中容易誤判。

例如：

| 情境           |       電壓 | 是否該停機 |
| ------------ | -------: | ----- |
| 單點 EMI noise | 9V，但只有一筆 | 不一定   |
| Sensor jump  | 9V，下一筆正常 | 不一定   |
| 連續硬體異常       | 多筆都超過 8V | 應該警示  |
| 溫度與電流同步升高    |  電壓不一定最高 | 需要稽核  |

所以本專案使用動態統計，而不是單純固定閾值。

---

## 3. SPC 與 Z-Score 概念

SPC 是 Statistical Process Control，統計製程管制。

在製造場景中，SPC 常用來判斷製程是否穩定。

本專案使用 Sliding Window 計算每台機台、每個 channel 在最近 10 筆資料內的：

* Rolling Average
* Rolling StdDev

接著計算 Z-Score：

```text
Z = (X - rolling_mean) / rolling_std
```

如果：

```text
ABS(Z) > 3
```

代表該點相對於近期資料窗口具有統計異常性。

---

## 4. 為什麼需要 Lag / Lead？

Z-Score 只能告訴我們某點很異常，但無法判斷它是單點 noise 還是真異常。

因此本專案使用：

```sql
LAG(voltage)
LEAD(voltage)
```

觀察前一點與後一點。

### False Positive Noise

條件：

* 當前點 voltage > 8
* ABS(z_score) > 3
* 前一點正常
* 後一點正常

代表這比較像單點雜訊。

標記為：

```text
is_noise = 1
```

---

### True Anomaly

條件：

* 當前點 voltage > 8
* ABS(z_score) > 3
* 前一點或後一點也在高電壓區

代表這比較像連續異常。

標記為：

```text
is_true_anomaly = 1
```

---

### False Negative Suspect

條件：

* 電壓尚未突破最高門檻
* 但溫度升高
* 測試時間拉長

代表可能是早期異常或模糊風險。

標記為：

```text
is_suspect = 1
```

---

## 5. SQL Pipeline 階段說明

本專案 SQL 使用多層 CTE。

### Stage 1：src_cleaned

將 raw data 中的 Sensor Disconnect 值轉為 NULL。

```text
-99.0 → NULL
```

這一步不在 Landing Zone 做，而是在 Transformation Layer 做。

---

### Stage 2：spc_rolling

使用 Window Functions 計算：

* rolling_avg
* rolling_std

依照：

```text
machine_id + channel_id
```

分組，避免不同機台與不同通道的訊號互相污染。

---

### Stage 3：z_score_calc

計算：

* z_score
* prev_volt
* next_volt

也就是為每一點建立統計異常程度與前後時序關係。

---

### Stage 4：anomaly_governance

產生三個核心治理欄位：

```text
is_noise
is_true_anomaly
is_suspect
```

這是本專案的工業資料治理核心。

---

### Stage 5：downsampling_aggregation

將高頻資料依分鐘級窗口聚合。

輸出：

* avg_voltage
* max_voltage
* avg_current
* avg_temperature
* total_raw_points
* is_noise_intercepted
* is_true_anomaly_triggered
* is_fn_suspect_flagged

---

### Stage 6：Upsert

使用：

```sql
ON CONFLICT (metric_pk) DO UPDATE
```

確保管線重跑不會造成資料重複。

---

## 6. 為什麼需要 Idempotency？

真實資料管線常會重跑。

例如：

* Airflow task retry
* DB connection timeout
* CSV 重送
* Network issue
* Job failure recovery

如果沒有 Idempotency，同一批資料可能被重複寫入，造成 KPI 失真。

本專案使用：

```text
MD5(machine_id + channel_id + test_station + lot_id + window_timestamp)
```

作為唯一主鍵。

這能確保同一個業務粒度只會有一筆事實資料。

---

## 7. SQL 檔案

本階段 SQL 放在：

```text
sql/transform_spc_pipeline.sql
```

---

## 8. 執行 SQL Pipeline

在專案根目錄執行：

```bash
docker exec -i chroma-postgres psql -U chroma_admin -d chroma_ate_db < sql/transform_spc_pipeline.sql
```

---

## 9. 驗證結果

進入 PostgreSQL：

```bash
docker exec -it chroma-postgres psql -U chroma_admin -d chroma_ate_db
```

查詢事實表：

```sql
SELECT COUNT(*)
FROM fct_machine_metrics;
```

查詢治理結果：

```sql
SELECT
    machine_id,
    SUM(total_raw_points) AS total_raw_points,
    SUM(is_noise_intercepted) AS noise_intercepted,
    SUM(is_true_anomaly_triggered) AS true_anomaly_triggered,
    SUM(is_fn_suspect_flagged) AS fn_suspect_flagged,
    ROUND(AVG(avg_voltage), 3) AS avg_clean_voltage
FROM fct_machine_metrics
GROUP BY machine_id
ORDER BY machine_id;
```

查詢真異常：

```sql
SELECT
    window_timestamp,
    machine_id,
    test_station,
    channel_id,
    lot_id,
    avg_voltage,
    max_voltage,
    avg_temperature,
    is_true_anomaly_triggered
FROM fct_machine_metrics
WHERE is_true_anomaly_triggered > 0
ORDER BY window_timestamp;
```

查詢攔截的 noise：

```sql
SELECT
    window_timestamp,
    machine_id,
    channel_id,
    lot_id,
    is_noise_intercepted,
    avg_voltage,
    max_voltage
FROM fct_machine_metrics
WHERE is_noise_intercepted > 0
ORDER BY window_timestamp;
```

---

## 10. 面試說明重點

這一階段可以這樣說明：

> 本專案的核心不只是偵測異常，而是分辨異常的性質。
> 我使用 PostgreSQL Window Functions 計算每台機台、每個 channel 的 Rolling Average 與 Rolling StdDev，再用 Z-Score 判斷統計異常。
> 但我沒有只停在 Z-Score，而是進一步使用 Lag / Lead 檢查前後時間點，將單點突波標記為 False Positive noise，將連續異常標記為 True Anomaly。
> 最後透過 Downsampling 與 Upsert 建立可重跑、不重複、可視覺化的 SSoT Fact Table。

---

## 11. 本階段產出

完成後會建立：

```text
fct_machine_metrics
```

這張表會提供給 Day 5 Streamlit Dashboard 使用。

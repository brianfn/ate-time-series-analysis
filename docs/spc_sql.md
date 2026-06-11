# SPC / Z-Score / SQL Window Functions 資料治理

## 1. 階段目標

使用 PostgreSQL SQL Pipeline，將 `raw_machine_logs` 轉換成可分析、可查詢、可視覺化的 SSoT Fact Table：

```text
fct_machine_metrics
```

此階段會完成：

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

## 2. 固定閾值的限制

若使用：

```sql
WHERE voltage > 8
```

在工業時間序列資料中，單一閾值容易忽略訊號的上下文，進而造成誤判或漏判。

| 情境           | 資料特徵                | 判斷方式       |
| ------------ | ------------------- | ---------- |
| 單點 EMI noise | 電壓短暫升高，但只出現一筆       | 不應立即視為硬體異常 |
| Sensor jump  | 電壓瞬間跳高，下一筆恢復正常      | 需與前後資料一起判斷 |
| 連續硬體異常       | 多筆資料持續超過 8V         | 應列為明確警示    |
| 溫度與電流同步升高    | 電壓未必達到最高值，但其他訊號同步惡化 | 需進入稽核流程    |

因此，異常治理不只依賴固定閾值，而是加入動態統計與時間序列脈絡，讓系統能區分短暫雜訊、感測器跳點與真正需要處理的異常。


---

## 3. SPC 與 Z-Score 概念

SPC（Statistical Process Control，統計製程管制）常用於製造場景，用來觀察製程是否維持在穩定狀態。

在這套資料治理流程中，每台機台、每個 channel 都會以 Sliding Window 方式計算最近 10 筆資料的統計基準：

* Rolling Average
* Rolling StdDev

再依據近期平均值與標準差計算 Z-Score：

```text
Z = (X - rolling_mean) / rolling_std
```

當 Z-Score 的絕對值超過 3 時：

```text
ABS(Z) > 3
```

代表該資料點相對於近期資料窗口出現明顯偏離，具有統計上的異常性。


---

## 4. Lag / Lead 與時間序列上下文

Z-Score 可以判斷單一資料點是否相對偏離近期統計基準，但僅靠當下數值，仍難以區分短暫雜訊與連續異常。

因此，資料治理流程會透過前後資料點補足時間序列上下文：

```sql
LAG(voltage)
LEAD(voltage)
```

透過觀察前一筆與後一筆資料，可以進一步判斷異常訊號是單點跳動，還是已經形成連續趨勢。

### False Positive Noise

當資料點同時符合以下條件：

* 當前 `voltage > 8`
* `ABS(z_score) > 3`
* 前一筆資料仍在正常範圍
* 後一筆資料也回到正常範圍

這類情境較接近單點雜訊，例如 EMI noise 或瞬間 sensor jump，不應直接視為連續硬體異常。

標記欄位：

```text
is_noise = 1
```

---

### True Anomaly

當資料點同時符合以下條件：

* 當前 `voltage > 8`
* `ABS(z_score) > 3`
* 前一筆或後一筆資料也處於高電壓區

這代表異常並非單點跳動，而是已經在相鄰資料中延續，較接近真正需要警示的連續異常。

標記欄位：

```text
is_true_anomaly = 1
```

---

### False Negative Suspect

有些資料雖然尚未突破最高電壓門檻，但其他訊號已經出現劣化跡象，例如：

* 溫度升高
* 測試時間拉長
* 同一機台或 channel 重複出現模糊異常

這類資料不會直接被視為正常，而是保留下來作為潛在風險，供後續稽核與工程分析。

標記欄位：

```text
is_suspect = 1
```


---

## 5. SQL Pipeline 階段說明

SQL Pipeline 採用多層 CTE 設計，將資料清洗、統計計算、異常治理與分鐘級聚合拆成不同階段，讓每一層的邏輯都能被追蹤與驗證。

### Stage 1：src_cleaned

將 raw data 中代表 Sensor Disconnect 或 Data Server Timeout 的特殊值轉為 `NULL`：

```text
-99.0 → NULL
```

這個轉換放在 Transformation Layer，而不是 Landing Zone。Landing Zone 保留原始資料樣貌，Transformation Layer 則負責將資料轉成後續分析可使用的格式。

---

### Stage 2：spc_rolling

透過 Window Functions 計算每個時間序列窗口內的統計基準：

* `rolling_avg`
* `rolling_std`

計算時依照以下欄位分組：

```text
machine_id + channel_id
```

這樣可以避免不同機台或不同 channel 的訊號被混在一起，造成統計基準互相污染。

---

### Stage 3：z_score_calc

在 rolling 統計基準的基礎上，進一步計算每一筆資料的異常程度與時序上下文：

* `z_score`
* `prev_volt`
* `next_volt`

其中 `z_score` 用來衡量該點相對於近期窗口的偏離程度，`prev_volt` 與 `next_volt` 則提供前後資料點的判斷依據。

---

### Stage 4：anomaly_governance

根據固定閾值、Z-Score 與前後資料點關係，產生三個核心治理欄位：

```text
is_noise
is_true_anomaly
is_suspect
```

這一層負責將原始異常訊號轉成可治理的判斷結果，用來區分單點雜訊、連續異常與潛在漏報風險。

---

### Stage 5：downsampling_aggregation

將高頻測試資料依分鐘級窗口進行聚合，降低資料量，同時保留異常治理結果。

輸出欄位包含：

* `avg_voltage`
* `max_voltage`
* `avg_current`
* `avg_temperature`
* `total_raw_points`
* `is_noise_intercepted`
* `is_true_anomaly_triggered`
* `is_fn_suspect_flagged`

這一層會將明細層的治理結果彙整到分鐘級事實資料，作為 Dashboard 與後續分析的主要資料來源。

---

### Stage 6：upsert

最後透過 upsert 寫入目標 Fact Table：

```sql
ON CONFLICT (metric_pk) DO UPDATE
```

當同一個業務粒度的資料已存在時，會更新既有紀錄，而不是新增重複資料。

---

## 6. Idempotency 與唯一業務粒度

真實資料管線經常會因為重試或補資料而重跑，例如：

* Airflow task retry
* DB connection timeout
* CSV 重送
* Network issue
* Job failure recovery

如果缺少 Idempotency，同一批資料可能被重複寫入，導致 KPI、異常次數與 Dashboard 指標失真。

因此，Fact Table 使用以下欄位組合產生唯一主鍵：

```text
MD5(machine_id + channel_id + test_station + lot_id + window_timestamp)
```

這組 key 對應到一個明確的業務粒度：同一台機台、同一個 channel、同一個測試站、同一個 lot，在同一個分鐘級時間窗口內，只會產生一筆事實資料。

透過這種設計，即使 Pipeline 重跑，也能確保資料結果可重現、不重複，並維持 SSoT Fact Table 的一致性。

---

## 7. SQL 檔案位置

SPC Pipeline SQL 位於：

```text
sql/transform_spc_pipeline.sql
```

---

## 8. SQL Pipeline 執行方式

在專案根目錄執行下列指令，將 SQL Pipeline 套用至 PostgreSQL：

```bash
docker exec -i chroma-postgres psql -U chroma_admin -d chroma_ate_db < sql/transform_spc_pipeline.sql
```

---

## 9. 結果驗證

可透過 PostgreSQL 查詢 Fact Table 與治理結果，確認 Pipeline 輸出是否符合預期。

進入 PostgreSQL：

```bash
docker exec -it chroma-postgres psql -U chroma_admin -d chroma_ate_db
```

### Fact Table 筆數

```sql
SELECT COUNT(*)
FROM fct_machine_metrics;
```

### 機台層級治理摘要

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

### True Anomaly 查詢

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

### Noise 攔截查詢

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

## 10. 階段產出

```text
fct_machine_metrics
```

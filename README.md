## **ATE 測試設備高頻時間序列數據流之 SPC 動態過濾與False Positive治理管線(ATE-SPC-Pipeline)**

### 專案簡介
模擬半導體測試設備在量測電壓、電流與溫度時產生的高頻 Raw Data，並建立一套從
**Data Generation → Data Ingestion → SQL Transformation → SPC Governance → SSoT Fact Table → Streamlit Dashboard** 的端到端資料管線。
當測試設備產生單點突波時，若傳統量測系統僅依賴固定閾值進行判斷，例如 WHERE voltage > 8.0V，就容易將短暫的環境噪音誤判為真實異常，形成 False Positive，將環境噪音誤判為真實異常，導致 MES 系統誤報、產線無故停機與工程師不必要的排查成本，以及整體稼動率下降。本專案的目標是建立一套能同時兼顧 降低 False Positive 與 避免 False Negative 的資料治理流程。此專案從高頻測試資料生成、資料載入、SQL 清洗轉換、SPC 統計治理，到建立可追溯的 SSoT Fact Table，最後透過 Streamlit Dashboard 呈現異常判斷、突波治理結果與機台訊號品質監控。

 ### 專案重點
* 使用 NumPy 模擬具備工業物理語境的 ATE 高頻時間序列資料
* 使用 Docker PostgreSQL 建立 Landing Zone
* 使用 Pandas Chunk-based Ingestion 避免大型 CSV 一次載入造成 OOM
* 使用 SQL Window Functions 建立 Rolling Average、Rolling StdDev、Z-Score
* 使用 Lag / Lead 判斷前後時間點，區分 False Positive 與 True Anomaly
* 使用 Downsampling 將高頻資料轉為可查詢的分鐘級 Fact Table
* 使用 MD5 Hash Key + `ON CONFLICT DO UPDATE` 建立 Idempotent Pipeline
* 使用 Streamlit + Plotly 建立 Data Product Dashboard
* 專案語境對應 ATE、MES、SPC、半導體測試、智慧製造資料工程

## 🏗️ 1.架構圖 (Data Pipeline Architecture)

```text
[1. Data Generation]     [2. DB Pushdown Governance]    [3. Production Analytics]
   +-----------------------+         +-------------------------+         +------------------------+
   |   Chroma ATE Engine   |         | PostgreSQL Engine (DB)  |         |   Streamlit Frontend   |
   | (High-Freq Simulator) |         |                         |         |                        |
   |   - Voltage & Temp    | ------> | - Window Functions      | ------> | - Real-time GIF Demo   |
   |   - Noise Injection   |  (Bulk) | - Rolling Z-Score (3σ)  | (Mock)  | - Multi-Dimension KPI  |
   |   - PII Data Masking  |         | - Auto-Recovery Flags   |         | - Offline Audit View   |
   +-----------------------+         +-------------------------+         +------------------------+
               |                                  |
               v                                  v
     [ raw_machine_logs ]               [ fct_machine_metrics ] 
       (百萬級原始日誌)                     (自癒優化事實表)
                                                  |
                                                  v (Export Local Only)
                                        [ Offline Audit Snapshot ]
                                        (不提交至 Git, 防止資安外洩)


## Repo 結構

```text
ate-spc-false-positive-pipeline/
│
├── README.md
├── requirements.txt
│
├── src/
│   ├── generate_machine_ts_data.py
│   ├── ingest_raw_to_landing.py
│   └── app_dashboard.py
│
├── sql/
│   └── transform_spc_pipeline.sql
│
├── docs/
│   ├── day1_data_gen.md
│   ├── day2_ingestion.md
│   ├── day3_4_spc_sql.md
│   └── day5_dashboard.md
│
├── assets/
│   ├── architecture.png
│   └── dashboard_screenshot.png
│
└── data/
    └── .gitkeep
```
---
## 解決的問題

### 1. False Positive 誤報
ATE 測試設備可能出現單點突波，例如電壓瞬間跳到 9V，但下一筆資料立刻恢復正常。
這種情況可能來自：
* 電磁干擾 EMI
* Sensor Jump
* 接線瞬間不穩
* 資料採集瞬間異常
* 通訊雜訊
傳統固定閾值會把它判定成 FAIL，但實際上不一定代表產品或機台真的異常。


### 2. True Anomaly 真異常
如果電壓連續多個時間點異常，並伴隨電流、溫度、測試時間同步上升，就更可能是真實硬體異常。
例如：
* 元件過熱
* Power device breakdown
* 測試站異常
* 接觸阻抗異常
* 機台測試條件失控

### 3. False Negative 潛在漏報
有些資料沒有超過硬性閾值，但多個特徵已經出現風險。
例如：
* 電壓尚未破表
* 溫度開始上升
* test_duration_ms 拉長
* 同一通道重複出現模糊異常
本專案將這類資料標記為 `is_fn_suspect_flagged`，放入冷路徑稽核區，供工程師後續分析。

## Data Pipeline Flow

### 1：Data Generation
使用 Python / NumPy 模擬 100,000 筆 ATE 高頻時間序列資料。
模擬內容包含：
* 正常 5V 波形
* 單點突波 noise
* 連續真異常 true_fail
* Sensor disconnect `-99.0`
* machine_id / channel_id / lot_id / wafer_id_unit_id 等追溯欄位
詳細說明請見：
[docs/data_gen.md](docs/data_gen.md)

### 2：Data Ingestion
使用 Docker PostgreSQL 建立 Landing Zone，並使用 Pandas Chunk-based Streaming 將 CSV 分批寫入 `raw_machine_logs`。
重點：
* 避免一次載入大型 CSV 造成記憶體壓力
* 模擬 Data Server 接收 ATE log
* 保留原始資料，不在 Landing Zone 過早清洗

詳細說明請見：
[docs/ingestion.md](docs/ingestion.md)

### 3：SPC SQL Transformation
使用 PostgreSQL SQL Pipeline 進行資料治理。
核心邏輯包含：
* `AVG() OVER()` Rolling Average
* `STDDEV() OVER()` Rolling StdDev
* Z-Score
* `LAG()` / `LEAD()` 前後時序關聯
* False Positive noise filtering
* True anomaly detection
* False negative suspect flagging
* Downsampling
* Upsert Idempotency

詳細說明請見：
[docs/spc_sql.md](docs/spc_sql.md)

### 4：Dashboard
使用 Streamlit + Plotly 建立資料產品化看板。
Dashboard 顯示：
* False Positive 攔截次數
* 預估避免誤停機成本
* True Anomaly 告警
* FN Suspect 冷路徑稽核
* 平均電壓與最高電壓趨勢圖

詳細說明請見：
[docs/day5_dashboard.md](docs/day5_dashboard.md)

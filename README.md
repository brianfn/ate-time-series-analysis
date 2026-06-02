這是一份可以直接複製貼上的完整 Markdown 原始碼。我已經將順序調整為最具邏輯性的「痛點先行 ──> 架構圖 ──> 核心邏輯 ──> 部署說明」，並格式化好程式碼區塊（Code Blocks）與引言，你可以直接全選複製到你的 `README.md` 中：

```markdown
# 📈 ATE High-Frequency Time-Series Data Stream SPC & False Positive Governance Pipeline

> **ATE 測試設備高頻時間序列數據流之 SPC 動態過濾與 False Positive 治理管線**

---

## 📖 專案背景與核心痛點 (Background & Pain Points)

在半導體自動化測試（ATE）無塵室中，測試機台會以高頻頻率採集功率元件的物理訊號。然而，現場不可避免地存在**環境電磁干擾 (EMI)**，常導致感測器產生孤立的**「單點隨機突波 (Spike)」**。

* **傳統做法的災難**：傳統量測系統僅依賴死板的靜態閾值限制（如 `WHERE voltage > 8.0V`），會將這些環境雜訊誤判為產品不良，進而導致製造執行系統（MES）頻繁發出誤報警、產線冤枉停機、工廠稼動率嚴重下滑。這在工業上被稱為 **False Positive（偽陽性）治理失敗**。
* **過度過濾的連連看災難**：若一味抹平突波，又極易陷入 **False Negative（漏報/真瑕疵晶片流出）** 的系統性風險。

本專案全方位遵循**數據生命週期演進（Ingestion ──> SSoT 建模 ──> Data Product 變現）**，實作出一套兼顧「過濾誤報」與「防止漏報」的雙軌動態治理中台。

### 🔄 數據演進生命週期
```text
[1. NumPy 模擬機台高頻訊號] ──> [2. Docker Postgres Landing Zone 接入]
                                                       │
                                                       ▼
[4. Streamlit 數據資產變現消費] ──> [3. SQL 進階視窗函數 (SPC Z-Score 智慧精煉)]

```

---

## 🏗️ 1. 架構圖 (Data Pipeline Architecture)

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

```

---

## 🛠️ 2. 技術棧與關鍵核心實現 (Tech Stack & Core Logic)

* **Data Ingestion**: Python (NumPy) 模擬高頻、具 EMI 雜訊之物理訊號，並導入 PII 數據去識別化遮罩。
* **Data Storage**: PostgreSQL (基於 Docker 容器化部署 Landing Zone)。
* **Data Governance**: 精煉 SQL 進階視窗函數（Window Functions），實作移動視窗 Z-Score ($3\sigma$) 動態閾值，達成智慧型 False Positive 自癒過濾。
* **Data Product**: Streamlit 建立多維度 KPI 數據監控面板，實現數據資產變現與消費。

---

## 🚀 3. 快速開始與部署說明 (Quick Start)

*(此處可根據實際腳本名稱修改)*

1. **啟動數據庫環境**
```bash
docker-compose up -d

```


2. **執行高頻訊號模擬與寫入 (Bulk Insert)**
```bash
python data_simulator.py

```


3. **啟動 Streamlit 前端看板**
```bash
streamlit run app.py

```



---

## 🔒 4. 本地審計與資安規範 (Security & Compliance)

> ⚠️ **重要安全性提醒**：為了防範無塵室生產環境敏感數據外洩，本專案設有嚴格的資安分流機制。

* 核心事實表所導出的 **`Offline Audit Snapshot` (離線審計快照)** 已強制加入 `.gitignore`。
* 任何包含真實機台參數、產線編號等敏感快照**絕不提交至 Git 遠端數據庫**，僅留存於本地安全網域供線下稽核。

```

```
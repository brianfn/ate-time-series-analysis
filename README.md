 
# 📈 Industrial ATE High-Frequency Time-Series Data Stream SPC & False Positive Governance Pipeline


> **ATE 測試設備高頻時間序列數據流之 SPC 動態過濾與False Positive治理管線**
```text
本專案專為半導體自動測試設備（ATE）的高頻時序數據設計。從地端機台的數據生成、高吞吐落底、資料庫下沉（Pushdown）統計學清洗，到最終的資料治理與視覺化展示，完整實踐了 **DataOps 的核心精神與單一真實來源（SSoT）架構**。

[Day 1: NumPy 模擬機台高頻訊號] —-> [Day 2: Docker Postgres Landing Zone 接入]
|
▼
[Day 5: Streamlit 數據資產變現消費] <—- [Day 3&4: SQL 進階視窗函數 (SPC Z-Score 智慧精煉)]
```

---

## 🏗️ 1. 全專案資料架構圖 (Data Pipeline Architecture)

本架構遵循 **"Code and Data Separation"（代碼與數據分離）** 與 **安全隔離原則**，確保敏感的機台生產數據不外洩，同時保障管線的**冪等性（Idempotency）**。

```text
[Day 1-2: Data Generation]     [Day 3-4: DB Pushdown Governance]    [Day 5: Production Analytics]
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
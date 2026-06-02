## 1. 本階段目標

Day 5 的目標是將 Day 3 & Day 4 產出的 `fct_machine_metrics` 轉換成可互動 Dashboard。

資料工程不只是在資料庫中建立表格，也需要讓使用者理解資料治理成果。本專案使用：

* Streamlit
* Plotly
* PostgreSQL
* Pandas

建立一個簡易但完整的工業資料監控看板。

---

## 2. Dashboard 主要功能

Dashboard 包含四個核心區塊：

### 2.1 KPI 區

顯示：

* False Positive Noise 攔截次數
* 預估避免誤停機成本
* True Anomaly 次數
* False Negative Suspect 次數

---

### 2.2 電壓趨勢圖

顯示：

* `avg_voltage`
* `max_voltage`

概念：

* `max_voltage` 可以看到原始高電壓尖峰
* `avg_voltage` 是經過 SQL noise filtering 後的平均電壓

這可以視覺化展示：

> 管線有能力把單點 noise 排除，不讓平均趨勢被污染。

---

### 2.3 MES True Anomaly Alert

如果：

```text
is_true_anomaly_triggered > 0
```

Dashboard 會顯示警示區塊，代表可能需要 MES 或製程工程師介入。

---

### 2.4 False Negative Suspect Review

如果：

```text
is_fn_suspect_flagged > 0
```

Dashboard 會列出潛在漏報風險。

這代表雖然資料尚未達到即時停機標準，但已經值得工程師進一步稽核。

---

## 3. 為什麼要做 Dashboard？

面試作品集不能只有後端 pipeline。

Dashboard 的價值是把技術成果轉成使用者看得懂的語言。

例如：

| 技術成果                      | Dashboard 呈現            |
| ------------------------- | ----------------------- |
| noise filtering           | 攔截多少次 False Positive    |
| Z-Score anomaly detection | 找到多少 True Anomaly       |
| FN suspect logic          | 哪些資料需要二次稽核              |
| SSoT fact table           | 可被穩定查詢的治理結果             |
| Data Engineering          | 對 MES / 製程 / 管理者有用的資料產品 |

---

## 4. 程式檔案

本階段程式放在：

```text
src/app_dashboard.py
```

---

## 5. 安裝套件

```bash
pip3 install streamlit plotly pandas sqlalchemy psycopg2-binary
```

---

## 6. 啟動 Dashboard

在專案根目錄執行：

```bash
streamlit run src/app_dashboard.py
```

開啟瀏覽器：

```text
http://localhost:8501
```

---

## 7. Dashboard 資料來源

Dashboard 從 PostgreSQL 讀取：

```text
fct_machine_metrics
```

主要 query：

```sql
SELECT 
    window_timestamp,
    machine_id,
    test_station,
    channel_id,
    lot_id,
    avg_voltage,
    max_voltage,
    avg_current,
    avg_temperature,
    total_raw_points,
    is_noise_intercepted,
    is_true_anomaly_triggered,
    is_fn_suspect_flagged
FROM fct_machine_metrics
ORDER BY window_timestamp DESC;
```

---

## 8. 預期畫面

Dashboard 應該包含：

1. 頁面標題
   工業級 ATE 測試設備高頻數據流之 SPC 動態過濾與偽陽性治理管線

2. Sidebar filter

   * machine_id
   * lot_id

3. KPI cards

   * False Positive Noise Intercepted
   * Estimated Avoided False Stop Cost
   * True Anomaly Triggered
   * FN Suspect Flagged

4. Plotly line chart

   * avg_voltage
   * max_voltage

5. MES Alert table

   * 顯示 true anomaly events

6. FN Suspect table

   * 顯示 suspect events

---

## 9. 預估避免誤停機成本的說明

Dashboard 中可以使用簡單估算：

```text
estimated_savings = total_noise_intercepted * 50000
```

這裡的 NT$50,000 只是作品集展示用假設。

正式 README 或面試時應說明：

> 此金額僅作為資料產品化展示用途，實際停機成本需依照產線、設備、產品價值與停機時間重新評估。

這樣比較專業，也避免看起來像誇大。

---

## 10. 面試說明重點

這一階段可以這樣說明：

> 我使用 Streamlit 將後端 SQL Fact Table 轉換成可互動 Dashboard。Dashboard 不只是畫圖，而是將資料治理結果轉成製造現場能理解的語言，例如 False Positive 攔截次數、True Anomaly 告警、潛在漏報稽核與預估避免停機成本。這代表我不只會寫 ETL，也能將資料工程成果產品化，讓製程、MES、研發或管理者能直接使用。

---

## 11. 本階段產出

完成 Day 5 後，會得到：

```text
Streamlit Dashboard
```

此 Dashboard 是整個作品集的展示入口。

---

## 12. 可延伸功能

未來 Dashboard 可加入：

* 自動刷新
* Machine health score
* Channel-level drill down
* Lot-level root cause analysis
* True anomaly event timeline
* SPC control chart
* Export report CSV
* Grafana integration
* Alert webhook
* MES API simulation

---

## 13. 完整專案總結

Day 5 完成後，本專案形成完整資料生命週期：

```text
Data Generation
→ Data Ingestion
→ SQL Transformation
→ SSoT Fact Table
→ Dashboard
```

核心價值是：

> 將 ATE 高頻量測資料轉換成可治理、可查詢、可解釋、可展示的工業資料產品。

# Day 1：ATE 高頻時間序列資料模擬與物理語境設計

## 1. 本階段目標

Day 1 的目標是建立本專案的資料來源。

我們使用 Python、NumPy、Pandas 模擬 ATE 測試設備在高頻量測過程中產生的 Raw Data。

這不是一般電商、鐵路或金融資料，而是針對半導體測試設備設計的工業時間序列資料。

資料會包含：

* 正常電壓波形
* 電流訊號
* 溫度訊號
* 單點突波 noise
* 連續真異常 true_fail
* Sensor disconnect 髒資料
* machine_id / channel_id / lot_id / wafer_id_unit_id 等追溯欄位

---

## 2. 為什麼要自己模擬資料？

在 ATE、智慧製造、半導體測試場景中，真實資料通常不容易公開取得。

原因包括：

* 客戶資料保密
* 產線資料涉及良率
* 測試資料涉及產品規格
* 機台 log 可能含有設備參數與機密測試條件

因此，作品集專案可以用模擬資料，但重點是資料必須有合理的物理語境。

本專案不是隨機產生一堆數字，而是刻意模擬以下工業場景：

1. 正常測試訊號
2. 感測器瞬間跳動
3. EMI 電磁干擾
4. 真實硬體異常
5. Sensor disconnect
6. 測試通道與批號追溯

---

## 3. 資料粒度 Data Grain

本專案的每一筆資料代表：

> 某台 ATE 機台，在某個測試站、某個通道，於某個時間點，對某個 wafer / unit 進行測試時產生的一筆量測紀錄。

主要欄位如下：

| 欄位               | 說明                 |
| ---------------- | ------------------ |
| timestamp        | 量測時間               |
| machine_id       | ATE 機台 ID          |
| test_station     | 測試站                |
| channel_id       | 測試通道               |
| lot_id           | 批號                 |
| wafer_id_unit_id | Wafer 或 Unit 追溯 ID |
| voltage          | 電壓                 |
| current          | 電流                 |
| temperature      | 溫度                 |
| test_duration_ms | 測試耗時               |
| pass_fail        | 原始機台判斷             |
| error_code       | 原始錯誤碼              |
| anomaly_type     | 模擬資料標籤             |

---

## 4. 模擬情境說明

### 4.1 正常資料 Normal Signal

正常電壓以 5.0V 為中心，加入微幅 sine wave 與 Gaussian noise。

這代表真實設備量測時，即使狀態正常，訊號也不會完全平坦。

可能原因包括：

* 電源微幅波動
* 測試治具接觸差異
* 元件特性變化
* 量測解析度誤差

---

### 4.2 False Positive Noise

False Positive 是本專案的核心治理目標。

模擬方式：

* 隨機挑選部分資料點
* 將電壓瞬間拉高到 8.5V 至 9.5V
* 下一個時間點立即恢復正常

這種情境代表：

* EMI 電磁干擾
* Sensor Jump
* 瞬間接觸不穩
* ADC 採樣異常
* Data Server 接收雜訊

如果工程師只用固定閾值判斷：

```sql
WHERE voltage > 8
```

這些單點 noise 就會被誤判為 FAIL。

---

### 4.3 True Anomaly

真異常不是單點，而是連續多個時間點異常。

模擬方式：

* 在固定區段注入連續 15 筆高電壓
* 同時拉高 current
* 同時拉高 temperature
* 同時增加 test_duration_ms

這比單點 noise 更接近真實硬體問題。

可能代表：

* power device breakdown
* 元件過熱
* 測試站失控
* 接觸阻抗異常
* 真正的測試 fail

---

### 4.4 Sensor Disconnect

工業資料中常看到特殊值代表異常狀態。

本專案使用：

```text
-99.0
```

代表 Sensor Disconnect 或 Data Server Timeout。

在 Landing Zone 中會保留這些原始值，後續 Transformation 階段再轉為 NULL。

這樣可以保留 Audit Trail，也符合原始資料層不過早清洗的原則。

---

## 5. 程式檔案

本階段程式碼放在：

```text
src/generate_machine_ts_data.py
```

主要功能：

1. 建立時間序列 timestamp
2. 建立 machine_id / station / channel / lot / wafer_id
3. 模擬 voltage / current / temperature
4. 注入 noise
5. 注入 true anomaly
6. 注入 sensor disconnect
7. 匯出 CSV

---

## 6. 執行方式

在專案根目錄執行：

```bash
python3 src/generate_machine_ts_data.py
```

預期產出：

```text
machine_raw_logs.csv
```

---

## 7. 預期資料量

預設產生：

```text
100,000 rows
```

時間間隔：

```text
0.01 seconds
```

也就是模擬 100Hz 的高頻量測資料。

> 注意：真實 ATE 或示波器資料可能更高頻，但作品集專案以 100,000 筆資料足以展示資料工程設計、SPC 邏輯與 Dashboard。

---

## 8. 建議檢查方式

可以用 Python 快速檢查：

```python
import pandas as pd

df = pd.read_csv("machine_raw_logs.csv")

print(df.head())
print(df.shape)
print(df["anomaly_type"].value_counts())
print(df[["voltage", "current", "temperature"]].describe())
```

你應該會看到：

* 大多數為 normal
* 少量 noise
* 少量 true_fail
* 少量 missing
* voltage 多數集中在 5V 附近
* noise 或 true_fail 區段會高於 8V
* missing 區段會出現 -99.0

---

## 9. 面試說明重點

這一階段可以這樣解釋：

> 我沒有使用一般網路上的 generic dataset，而是根據 ATE 測試設備的物理語境自行模擬資料。資料中包含正常電壓波形、單點 sensor noise、連續硬體異常與 sensor disconnect。這樣可以讓後續的資料管線不只是做 ETL，而是解決工業現場真正會遇到的 False Positive 與 True Anomaly 分辨問題。

---

## 10. 本階段產出

完成 Day 1 後，會得到：

```text
machine_raw_logs.csv
```

此檔案會作為 Day 2 PostgreSQL Landing Zone 的資料來源。

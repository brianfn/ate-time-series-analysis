
# docs/day2_ingestion.md

# Day 2：PostgreSQL Landing Zone 與 Chunk-based Ingestion

## 1. 本階段目標

Day 2 的目標是將 Day 1 產生的 `machine_raw_logs.csv` 接入 PostgreSQL。

我們會建立一個 Landing Zone 資料表：

```text
raw_machine_logs
```

這張表會保存原始機台 log，不在這一層做過度清洗。

---

## 2. 為什麼需要 Landing Zone？

在 Data Engineering 架構中，Landing Zone 是原始資料落地區。

它的任務是：

* 快速接收資料
* 保留原始樣貌
* 支援後續重跑與追溯
* 避免在資料進來的第一時間做過多商業邏輯

本專案會將以下資料原封不動寫入 PostgreSQL：

* normal waveform
* noise
* true_fail
* missing `-99.0`
* 原始 error_code
* 原始 pass_fail

這樣後續如果 SQL Transformation 邏輯改版，仍可從原始資料重新計算。

---

## 3. 為什麼使用 Chunk-based Ingestion？

如果資料很大，直接使用：

```python
df = pd.read_csv("machine_raw_logs.csv")
df.to_sql(...)
```

會有風險：

* CSV 太大時記憶體爆掉
* 單次寫入時間過長
* 失敗後不容易定位問題
* 無法模擬工業資料分批接入

因此本專案使用：

```python
pd.read_csv(csv_path, chunksize=20000)
```

讓資料一批一批寫入 PostgreSQL。

這種做法更接近實際資料工程中的 batch ingestion 或 micro-batch ingestion。

---

## 4. 啟動 PostgreSQL

使用 Docker 啟動 PostgreSQL：

```bash
docker run --name chroma-postgres \
  -e POSTGRES_USER=chroma_admin \
  -e POSTGRES_PASSWORD=chroma_pwd_2026 \
  -e POSTGRES_DB=chroma_ate_db \
  -p 5432:5432 \
  -d postgres:15-alpine
```

檢查容器：

```bash
docker ps
```

如果容器已存在但停止：

```bash
docker start chroma-postgres
```

---

## 5. 安裝套件

```bash
pip3 install sqlalchemy psycopg2-binary pandas
```

---

## 6. 程式檔案

本階段程式碼放在：

```text
src/ingest_raw_to_landing.py
```

主要功能：

1. 檢查 `machine_raw_logs.csv` 是否存在
2. 建立 PostgreSQL connection engine
3. 使用 Pandas Chunk Reader 分批讀取 CSV
4. 使用 `to_sql()` 寫入 PostgreSQL
5. 第一批使用 `replace`
6. 後續批次使用 `append`
7. 印出每批寫入時間與吞吐量

---

## 7. 執行方式

在專案根目錄執行：

```bash
python3 src/ingest_raw_to_landing.py
```

預期結果：

```text
raw_machine_logs table created
100,000 rows inserted
```

---

## 8. 驗證資料

進入 PostgreSQL：

```bash
docker exec -it chroma-postgres psql -U chroma_admin -d chroma_ate_db
```

查詢筆數：

```sql
SELECT COUNT(*) FROM raw_machine_logs;
```

預期：

```text
100000
```

檢查部分資料：

```sql
SELECT *
FROM raw_machine_logs
LIMIT 10;
```

檢查 anomaly_type：

```sql
SELECT anomaly_type, COUNT(*)
FROM raw_machine_logs
GROUP BY anomaly_type
ORDER BY COUNT(*) DESC;
```

離開 PostgreSQL：

```sql
\q
```

---

## 9. 為什麼 Landing Zone 不先清洗 -99.0？

這是資料工程中很重要的觀念。

原始資料層應該盡量保留資料來源的原貌。

如果 Sensor Disconnect 在機台端就是用 `-99.0` 表示，那麼 Landing Zone 應該保留它。

原因：

* 保留 Audit Trail
* 支援資料稽核
* 支援重新計算
* 避免清洗邏輯污染原始資料
* 讓後續轉換層負責 business rule

因此本專案會在 Day 3 & 4 的 SQL Transformation 中，才將 `-99.0` 轉成 NULL。

---

## 10. 面試說明重點

這一階段可以這樣說明：

> 我使用 PostgreSQL 建立 Landing Zone，模擬 ATE Data Server 接收機台 Log。
> 為了避免大型 CSV 一次載入造成 Out of Memory，我使用 Pandas chunksize 進行 Chunk-based Ingestion。
> Landing Zone 保留原始資料，不在接入時過早清洗，這樣可以確保資料可追溯，也方便後續 SQL Pipeline 改版後重新計算。

---

## 11. 本階段產出

完成 Day 2 後，PostgreSQL 會有：

```text
raw_machine_logs
```

此表將作為 Day 3 & Day 4 SPC SQL Transformation 的資料來源。

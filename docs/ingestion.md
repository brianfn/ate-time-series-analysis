
# docs/Ingestion.md

# PostgreSQL Landing Zone 與 Chunk-based Ingestion

## 1. 本階段目標

將原始日誌資料（machine_raw_logs.csv）導入至 PostgreSQL

建立一個 Landing Zone 資料表：
`raw_machine_logs`

---
包含以下資料：

* normal waveform
* noise
* true_fail
* missing `-99.0`
* 原始 error_code
* 原始 pass_fail

這樣後續如果 SQL Transformation 邏輯改版，仍可從原始資料重新計算。

---

## 2. Chunk-based Ingestion

```python
pd.read_csv(csv_path, chunksize=20000)
```
讓資料一批一批寫入 PostgreSQL(batch ingestion)，避免大量資料單次寫入時間過長

---

## 3. 資料庫環境建置 (PostgreSQL)

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

`raw_machine_logs table created
100,000 rows inserted`

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

`100000`

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


---

## 9. 本階段產出

`
raw_machine_logs
`

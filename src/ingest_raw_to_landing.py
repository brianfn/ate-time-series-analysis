import pandas as pd
from sqlalchemy import create_engine
import time
import os

def ingest_csv_to_postgres(csv_path="../data/machine_raw_logs.csv", chunk_size=20000):
    print("Start ingesting data to PostgreSQL...")
    
    # 1. 檢查 source data 是否存在
    if not os.path.exists(csv_path):
        print(f"錯誤：找不到原始數據檔案 {csv_path}。")
        return

    # 2. 建立資料庫連線引擎 (Connection Engine)
    # 格式：postgresql://用戶名:密碼@主機:埠口/資料庫名
    DATABASE_URI = "postgresql://chroma_admin:chroma_pwd_2026@localhost:5432/chroma_ate_db"
    engine = create_engine(DATABASE_URI)
    
    target_table = "raw_machine_logs"
    total_rows_inserted = 0
    start_perf_time = time.time()
    
    print(f"🔗 成功連線至 PostgreSQL。目標暫存表：{target_table}")
    print(f"📦 串流防護啟動：每批次最大載入量 (Chunk Size) = {chunk_size} 筆...")

    # 3. 使用 Pandas TextFileReader 進行分塊串流讀取與寫入 (避免記憶體崩潰)
    # if_exists='replace' 代表第一次寫入時，若表存在就覆蓋重建；後續分塊則改用 'append'
    is_first_chunk = True
    
    with pd.read_csv(csv_path, chunksize=chunk_size) as reader:
        for i, chunk in enumerate(reader):
            chunk_start_time = time.time()
            
            # 決定寫入模式
            current_mode = "replace" if is_first_chunk else "append"
            
            # 將該批次數據推入 PostgreSQL
            chunk.to_sql(
                name=target_table,
                con=engine,
                if_exists=current_mode,
                index=False,
                method='multi'  # 使用批量插入機制，大幅提升寫入吞吐量
            )
            
            chunk_duration = time.time() - chunk_start_time
            total_rows_inserted += len(chunk)
            is_first_chunk = False
            
            print(f"   📥 [批次 {i+1}] 成功增量寫入 {len(chunk)} 筆資料，耗時: {chunk_duration:.2f} 秒.")

    total_duration = time.time() - start_perf_time
    throughput = total_rows_inserted / total_duration if total_duration > 0 else 0
    
    print("\n=========================================================================")
    print(f"✅ 數據接入成功")
    print(f"總落底筆數：{total_rows_inserted} 筆")
    print(f"總共花費時間：{total_duration:.2f} 秒")
    print(f"數據吞吐量 (Throughput)：{throughput:.0f} rows/sec")
    print("=========================================================================")

if __name__ == "__main__":
    ingest_csv_to_postgres()

# 10. 面試說明重點
# 這一階段可以這樣說明：
# 我使用 PostgreSQL 建立 Landing Zone，模擬 ATE Data Server 接收機台 Log。 
# 為了避免大型 CSV 一次載入造成 Out of Memory，我使用 Pandas chunksize 
# 進行 Chunk-based Ingestion。 Landing Zone 保留原始資料，不在接入時過早清洗，
# 這樣可以確保資料可追溯，也方便後續 SQL Pipeline 改版後重新計算。
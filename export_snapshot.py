# export_snapshot.py (在本地執行一次即可)
import pandas as pd
from sqlalchemy import create_engine

engine = create_engine("postgresql://chroma_admin:chroma_pwd_2026@localhost:5432/chroma_ate_db")
df = pd.read_sql("SELECT * FROM fct_machine_metrics", engine)
df.to_csv("fct_machine_metrics_snapshot.csv", index=False)
print("✅ 成功將事實表數據導出為 snapshot 快照，準備與代碼一同推送至 GitHub！")
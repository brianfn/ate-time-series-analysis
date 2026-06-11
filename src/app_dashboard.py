```python
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import plotly.express as px

# 設定 Streamlit 頁面基本資訊
st.set_page_config(
    page_title="ATE 測試資料治理 Dashboard",
    page_icon="📈",
    layout="wide"
)

# 建立 PostgreSQL 資料庫連線
DATABASE_URI = "postgresql://chroma_admin:chroma_pwd_2026@localhost:5432/chroma_ate_db"
engine = create_engine(DATABASE_URI)

@st.cache_data(ttl=5)  # 每 5 秒重新讀取一次資料，方便觀察資料更新
def load_fact_data():
    query = """
        SELECT 
            window_timestamp, machine_id, test_station, channel_id, lot_id,
            avg_voltage, max_voltage, avg_current, avg_temperature, total_raw_points,
            is_noise_intercepted, is_true_anomaly_triggered, is_fn_suspect_flagged
        FROM fct_machine_metrics
        ORDER BY window_timestamp DESC;
    """
    return pd.read_sql(query, engine)

# 從資料庫讀取整理後的 Fact Table 資料
try:
    df = load_fact_data()
except Exception as e:
    st.error(f"無法讀取資料庫資料，錯誤訊息：{e}")
    st.stop()

# =========================================================================
# 建立 Dashboard 主畫面
# =========================================================================

st.title("ATE 測試資料治理 Dashboard")
st.caption("以模擬高頻測試資料展示 SQL 清洗、SPC 判斷與異常標記結果")

if df.empty:
    st.warning("目前 Fact Table 尚未有資料，請確認 SQL Pipeline 是否已執行完成。")
else:
    # 側邊欄篩選條件
    st.sidebar.header("資料篩選")
    selected_machine = st.sidebar.selectbox(
        "選擇機台",
        options=["全部"] + list(df["machine_id"].unique())
    )
    selected_lot = st.sidebar.selectbox(
        "選擇 Lot ID",
        options=["全部"] + list(df["lot_id"].unique())
    )

    # 依照選擇條件篩選資料
    filtered_df = df.copy()
    if selected_machine != "全部":
        filtered_df = filtered_df[filtered_df["machine_id"] == selected_machine]
    if selected_lot != "全部":
        filtered_df = filtered_df[filtered_df["lot_id"] == selected_lot]

    # =========================================================================
    # 區塊一：資料治理摘要
    # =========================================================================

    total_noise_intercepted = int(filtered_df["is_noise_intercepted"].sum())
    total_true_anomalies = int(filtered_df["is_true_anomaly_triggered"].sum())
    total_fn_suspects = int(filtered_df["is_fn_suspect_flagged"].sum())

    total_processed = len(filtered_df) if len(filtered_df) > 0 else 1
    noise_reduction_rate = (total_noise_intercepted / total_processed) * 100

    CONVERSION_RATE = 0.02
    COST_PER_SHUTDOWN = 50000
    estimated_savings = int(total_noise_intercepted * CONVERSION_RATE * COST_PER_SHUTDOWN)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "可能的單點雜訊",
            f"{total_noise_intercepted} 筆",
            delta=f"約占 {noise_reduction_rate:.1f}%"
        )

    with col2:
        st.metric(
            "潛在誤判成本估算",
            f"NT$ {estimated_savings:,}",
            delta="以假設參數估算",
            delta_color="off"
        )

    with col3:
        st.metric(
            "連續異常標記",
            f"{total_true_anomalies} 筆",
            delta="依 SQL 規則判斷",
            delta_color="off"
        )

    with col4:
        st.metric(
            "潛在漏報觀察",
            f"{total_fn_suspects} 筆",
            delta="供後續檢查"
        )

    st.info(
        "此 Dashboard 使用模擬資料展示資料治理流程。"
        "上方指標用來觀察 SQL Pipeline 如何將高頻測試資料整理成可查詢的治理結果，"
        "其中成本估算為作品集中的假設情境，主要用來呈現資料工程結果如何轉換成可解讀的指標。"
    )

    st.markdown("---")

    # =========================================================================
    # 區塊二：電壓趨勢觀察
    # =========================================================================

    st.header("📈 電壓趨勢觀察")

    if not filtered_df.empty:
        chart_df = filtered_df.sort_values("window_timestamp")

        fig = px.line(
            chart_df,
            x="window_timestamp",
            y=["avg_voltage", "max_voltage"],
            labels={
                "value": "電壓 (V)",
                "window_timestamp": "時間",
                "variable": "欄位"
            },
            title="平均電壓與最高電壓趨勢",
            color_discrete_map={
                "max_voltage": "#EF553B",
                "avg_voltage": "#00CC96"
            }
        )
        fig.update_layout(
            hovermode="x unified",
            legend_orientation="h",
            legend_y=1.1
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("目前篩選條件下沒有可顯示的趨勢資料。")

    st.markdown("---")

    # =========================================================================
    # 區塊三：異常標記結果
    # =========================================================================

    left_col, right_col = st.columns(2)

    with left_col:
        st.subheader("連續異常標記結果")
        anomaly_events = filtered_df[filtered_df["is_true_anomaly_triggered"] > 0]

        if not anomaly_events.empty:
            st.warning(
                f"目前篩選結果中，有 {len(anomaly_events)} 筆資料被標記為連續異常。"
            )
            st.markdown(
                "這些資料符合 SQL Pipeline 中設定的異常規則，可作為後續檢查的候選資料。"
            )
            st.dataframe(
                anomaly_events[
                    [
                        "window_timestamp",
                        "machine_id",
                        "test_station",
                        "channel_id",
                        "is_true_anomaly_triggered",
                        "avg_temperature"
                    ]
                ],
                use_container_width=True
            )
        else:
            st.success("目前篩選結果中，沒有資料被標記為連續異常。")

    with right_col:
        st.subheader("潛在漏報觀察區")
        suspect_events = filtered_df[filtered_df["is_fn_suspect_flagged"] > 0]

        if not suspect_events.empty:
            st.warning(
                f"目前篩選結果中，有 {len(suspect_events)} 筆資料被標記為潛在漏報觀察。"
            )
            st.markdown(
                "這些資料尚未達到明確異常條件，但部分特徵已有變化，因此保留下來作為後續分析參考。"
            )
            st.dataframe(
                suspect_events[
                    [
                        "window_timestamp",
                        "machine_id",
                        "channel_id",
                        "lot_id",
                        "avg_voltage",
                        "avg_temperature",
                        "is_fn_suspect_flagged"
                    ]
                ],
                use_container_width=True
            )
        else:
            st.success("目前篩選結果中，沒有資料被標記為潛在漏報觀察。")
```

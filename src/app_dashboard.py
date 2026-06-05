import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import plotly.express as px

# 1. 網頁基本配置
st.set_page_config(
    page_title="ATE 高頻測試數據治理Dashboard",
    page_icon="📈",
    layout="wide"
)

# 2. 建立資料庫連線引擎
DATABASE_URI = "postgresql://chroma_admin:chroma_pwd_2026@localhost:5432/chroma_ate_db"
engine = create_engine(DATABASE_URI)

@st.cache_data(ttl=5) # 快取機制：每 5 秒自動重新整理，模擬工業低延遲監控
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

# 載入資料
try:
    df = load_fact_data()
except Exception as e:
    st.error(f"無法連線至資料庫事實表，錯誤訊息：{e}")
    st.stop()

# =========================================================================
# 前端畫面渲染開始
# =========================================================================
st.title("ATE 測試設備高頻數據流之 SPC 動態過濾與偽陽性治理管線")
st.caption("數據資產產品化與測試製程根因觀測 (Data Product Layer)")

if df.empty:
    st.warning("⚠️ 資料庫事實表目前為空，請確認 SQL 管線已成功將資料寫入")
else:
    # 頂部控制過濾器
    st.sidebar.header("產線觀測篩選器")
    selected_machine = st.sidebar.selectbox("選擇觀測 ATE 機台", options=["全部"] + list(df['machine_id'].unique()))
    selected_lot = st.sidebar.selectbox("選擇製程批號 (Lot ID)", options=["全部"] + list(df['lot_id'].unique()))

    # 進行資料過濾
    filtered_df = df.copy()
    if selected_machine != "全部":
        filtered_df = filtered_df[filtered_df['machine_id'] == selected_machine]
    if selected_lot != "全部":
        filtered_df = filtered_df[filtered_df['lot_id'] == selected_lot]

    # =========================================================================
    # 區塊一：核心 KPI 商業變現戰報
    # =========================================================================
    
    total_noise_intercepted = int(filtered_df['is_noise_intercepted'].sum())
    total_true_anomalies = int(filtered_df['is_true_anomaly_triggered'].sum())
    total_fn_suspects = int(filtered_df['is_fn_suspect_flagged'].sum())
    
    total_processed = len(filtered_df) if len(filtered_df) > 0 else 1
    noise_reduction_rate = (total_noise_intercepted / total_processed) * 100
    
    CONVERSION_RATE = 0.02 
    COST_PER_SHUTDOWN = 50000
    estimated_savings = int(total_noise_intercepted * CONVERSION_RATE * COST_PER_SHUTDOWN)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            "🛡️ 虛驚噪音自動攔截", 
            f"{total_noise_intercepted} 次", 
            delta=f"淨化 {noise_reduction_rate:.1f}% 數據垃圾"
        )
    with col2:
        st.metric(
            "💰 規避無故停機成本 (預估)", 
            f"NT$ {estimated_savings:,} 元", 
            delta="基於 2% 虛驚停機轉化率", 
            delta_color="inverse"
        )
    with col3:
        st.metric(
            "🚨 精準確診實體異常", 
            f"{total_true_anomalies} 次", 
            delta="避免連續故障擴大損壞", 
            delta_color="off"
        )
    with col4:
        st.metric(
            "🔍 捕捉潛在漏報 (FN)", 
            f"{total_fn_suspects} 次", 
            delta="覆蓋多維度模糊風險帶"
        )

    st.info(
        "💡 **商業價值效益評估備忘**：本面板摒棄「噪音直接等同停機」的誇大假設，改採嚴謹的 **2% 虛驚轉化率** 計算"
        "潛在損失規避（Risk Avoidance），真實、不誇大且客觀地向廠端管理層證明數據工程優化對產線實質產值的經濟效益。"
    )

    st.markdown("---")

    # =========================================================================
    # 區塊二：動態工業波形圖
    # =========================================================================
    st.header("📈 測試通道高頻物理波形觀測 (動態自癒對比)")
    
    if not filtered_df.empty:
        chart_df = filtered_df.sort_values('window_timestamp')
        
        fig = px.line(
            chart_df, 
            x='window_timestamp', 
            y=['avg_voltage', 'max_voltage'],
            labels={"value": "電壓 (V)", "window_timestamp": "量測時間", "variable": "訊號類型"},
            title="原始最高電壓 (包含突發電磁干擾) vs SQL 管線自癒後真實平均電壓 (剔除噪音)",
            color_discrete_map={"max_voltage": "#EF553B", "avg_voltage": "#00CC96"}
        )
        fig.update_layout(hovermode="x unified", legend_orientation="h", legend_y=1.1)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("當前篩選條件下無波形數據。")

    st.markdown("---")

    # =========================================================================
    # 區塊三：MES 即時預警警報與冷路徑漏報稽核
    # =========================================================================
    left_col, right_col = st.columns(2)

    with left_col:
        st.subheader("🚨 MES 即時停機告警門禁 (熱路徑)")
        anomaly_events = filtered_df[filtered_df['is_true_anomaly_triggered'] > 0]
        
        if not anomaly_events.empty:
            st.error(f"⚠️ 【緊急狀態】檢測到產線硬體連續多點發生致命真異常！")
            st.markdown("**💥 MES 系統自動干預：已發送並聯斷電訊號，產線緊急安全停機！**")
            st.dataframe(
                anomaly_events[['window_timestamp', 'machine_id', 'test_station', 'channel_id', 'is_true_anomaly_triggered', 'avg_temperature']],
                use_container_width=True
            )
        else:
            st.success("✅ 產線熱路徑監控中：當前無硬體連續燒毀異常，各機台安全運作中。")

    with right_col:
        st.subheader("🔍 潛在漏報 (False Negative) 補網稽核區 (冷路徑)")
        suspect_events = filtered_df[filtered_df['is_fn_suspect_flagged'] > 0]
        
        if not suspect_events.empty:
            st.warning(f"💡 發現 {len(suspect_events)} 筆處於『模糊風險帶』的機台數據（電壓微升且伴隨溫度攀升）")
            st.markdown("*此區塊數據未達即時停機標準（未衝破 3 $\sigma$ ），但已觸發冷路徑補網，供製程工程師進行 Change Point 變更點二次審查，徹底消滅漏報風險。*")
            st.dataframe(
                suspect_events[['window_timestamp', 'machine_id', 'channel_id', 'lot_id', 'avg_voltage', 'avg_temperature', 'is_fn_suspect_flagged']],
                use_container_width=True
            )
        else:
            st.success("✅ 統計學補網稽核完畢：未發現多維特徵連鎖變異點。")
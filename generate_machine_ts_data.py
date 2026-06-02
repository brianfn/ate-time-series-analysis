import pandas as pd
import numpy as np
import datetime
import hashlib

def generate_industrial_data(num_records=100000):
    print("🚀 Day 1: 開始模擬致茂 ATE 測試機台高頻時間序列數據...")
    
    # 1. 基礎時序與機台分類設定
    start_time = datetime.datetime(2026, 6, 1, 8, 0, 0)
    # 模擬 10 萬筆高頻數據，時間間隔設為 10 毫秒 (0.01 秒)，模擬高頻採集
    timestamps = [start_time + datetime.timedelta(seconds=i*0.01) for i in range(num_records)]
    
    machine_ids = ["CHROMA-ATE-01", "CHROMA-ATE-02"]
    test_stations = ["STATION-POWER-GATE", "STATION-DYNAMIC-RDS"]
    channels = ["CH-01", "CH-02", "CH-03", "CH-04"]
    lot_ids = ["LOT-20260601-01", "LOT-20260601-02"]
    
    # 隨機分配基礎分類特徵 (粒度設計)
    np.random.seed(42)  # 固定隨機種子以利 PoC 驗證
    mac_array = np.random.choice(machine_ids, num_records)
    station_array = np.random.choice(test_stations, num_records)
    channel_array = np.random.choice(channels, num_records)
    lot_array = np.random.choice(lot_ids, num_records)
    
    # 生成模擬的 Wafer / Unit ID (產品追溯)
    # 每 1000 筆數據代表測試完一顆晶片元件
    unit_ids = [f"WAF-{100000 + i // 1000:05d}" for i in range(num_records)]
    
    # 2. 物理訊號模擬 (以電壓、電流、溫度為核心事实)
    # 正常訊號：5.0V 的規律弦波 + 物理微幅震盪微幅噪聲
    time_axis = np.linspace(0, 100, num_records)
    base_voltage = 5.0 + 0.5 * np.sin(time_axis) + np.random.normal(0, 0.1, num_records)
    base_current = 1.2 + 0.1 * np.cos(time_axis) + np.random.normal(0, 0.02, num_records)
    base_temperature = 45.0 + 2.0 * np.sin(time_axis/5) + np.random.normal(0, 0.5, num_records)
    
    # 初始化標籤欄位
    anomaly_types = ["normal"] * num_records
    pass_fail = ["PASS"] * num_records
    error_codes = ["ERR-000"] * num_records  # ERR-000 代表正常運作無錯誤
    test_durations = np.random.randint(150, 200, num_records) # 正常測試耗時 150~200 毫秒
    
    # 3. 注入工業真實痛點訊號 (Spike, Noise, Drift, Missing Data)
    
    # 痛點 A：孤立單點隨機突波 (物理環境雜訊 / 偽陽性 False Positive 來源)
    # 隨機挑選 0.5% 的點，讓其電壓飆高至 9.0V 左右，但前後毫秒立刻恢復正常
    noise_indices = np.random.choice(num_records, int(num_records * 0.005), replace=False)
    for idx in noise_indices:
        base_voltage[idx] = np.random.uniform(8.5, 9.5)
        anomaly_types[idx] = "noise"
        # 傳統設備機台會因為靜態閾值直接誤判為 FAIL 並噴錯誤碼
        pass_fail[idx] = "FAIL"
        error_codes[idx] = "ERR-009-VOLT-LIMIT"
        
    # 痛點 B：連續 15 點電壓暴增 (硬體真燒毀 / 真異常 True Spike 來源)
    # 模擬在第 45000 筆到 45015 筆，機台元件真的過熱損壞，電壓與溫度持續飆高
    true_fail_start = 45000
    true_fail_duration = 15
    for i in range(true_fail_duration):
        curr_idx = true_fail_start + i
        base_voltage[curr_idx] = np.random.uniform(8.2, 8.8)
        base_current[curr_idx] = np.random.uniform(2.5, 3.0)  # 電流同時暴增
        base_temperature[curr_idx] = 85.0 + i * 2.0         # 溫度連鎖攀升
        test_durations[curr_idx] = np.random.randint(500, 600) # 異常導致測試時間拉長
        anomaly_types[curr_idx] = "true_fail"
        pass_fail[curr_idx] = "FAIL"
        error_codes[curr_idx] = "ERR-999-HARDWARE-BURN"

    # 痛點 C：通訊協定突發中斷斷線 (-99.0 數據品質髒資料)
    # 模擬在第 72000 筆到 72010 筆，感測器接線鬆脫或 Data Server 接收超時
    disconnect_start = 72000
    disconnect_duration = 10
    for i in range(disconnect_duration):
        curr_idx = disconnect_start + i
        base_voltage[curr_idx] = -99.0      # 工業常規：用特殊極端負數代表 Sensor 斷線
        base_current[curr_idx] = -99.0
        base_temperature[curr_idx] = -99.0
        anomaly_types[curr_idx] = "missing"
        pass_fail[curr_idx] = "ERROR"
        error_codes[curr_idx] = "ERR-404-SENSOR-DISCONNECT"

    # 4. 整合並建構 DataFrame
    df = pd.DataFrame({
        "timestamp": pd.to_datetime(timestamps),
        "machine_id": mac_array,
        "test_station": station_array,
        "channel_id": channel_array,
        "lot_id": lot_array,
        "wafer_id_unit_id": unit_ids,
        "voltage": np.round(base_voltage, 3),
        "current": np.round(base_current, 3),
        "temperature": np.round(base_temperature, 2),
        "test_duration_ms": test_durations,
        "pass_fail": pass_fail,
        "error_code": error_codes,
        "anomaly_type": anomaly_types
    })
    
    # 5. 匯出至專案地基 CSV
    output_filename = "machine_raw_logs.csv"
    df.to_csv(output_filename, index=False)
    
    print(f"📦 數據模擬完成！已成功生成 {len(df)} 筆高頻數據並匯出至 {output_filename}")
    print("💡 物理特徵已埋入：5V正常弦波、孤立單點噪音（偽陽性）、連續15點異常（真異常）、-99.0（斷線髒資料）。")

if __name__ == "__main__":
    generate_industrial_data()
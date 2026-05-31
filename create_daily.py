import gspread
import pandas as pd
import datetime

print("🔄 今日のタスクと「やり残し」を準備しています...")

# 1. 接続設定
gc = gspread.service_account(filename='credentials.json')
spreadsheet = gc.open('勉強ToDoデータベース')
master_ws = spreadsheet.worksheet('マスター')
daily_ws = spreadsheet.worksheet('デイリー')

jst = datetime.timezone(datetime.timedelta(hours=9))
now = datetime.datetime.now(jst)

# 🌟 現実のパソコンの時計を見る設定に戻しました
today_date_str = now.strftime("%Y-%m-%d")
weekday_list = ["月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]
today_weekday = weekday_list[now.weekday()]

# ==========================================
# STEP 1: 今のデイリーシートの状態を賢く取得する
# ==========================================
daily_records = daily_ws.get_all_records()
if daily_records:
    df_daily = pd.DataFrame(daily_records)
    keep_mask = (df_daily["ステータス"] != "完了") | (df_daily["ステータス_最終更新日時"].astype(str).str.startswith(today_date_str))
    df_daily_kept = df_daily[keep_mask].copy()
else:
    df_daily_kept = pd.DataFrame()

# ==========================================
# STEP 2: マスターから「今日のタスク」を取得する
# ==========================================
master_records = master_ws.get_all_records()
df_master = pd.DataFrame(master_records)
df_today = df_master[df_master["曜日"].isin([today_weekday, "毎日"])].copy()

df_today["ステータス"] = "未完了"
df_today["ステータス_最終更新日時"] = ""

# ==========================================
# STEP 3: 新しいタスクと、今の状態を上書き合体！
# ==========================================
if not df_daily_kept.empty:
    df_combined = pd.concat([df_today, df_daily_kept], ignore_index=True)
    df_combined = df_combined.drop_duplicates(subset=["対象者", "科目", "タスク名"], keep="last")
else:
    df_combined = df_today

df_combined = df_combined.fillna("")

# ==========================================
# STEP 4: デイリーシートに書き込む
# ==========================================
daily_ws.clear()
if not df_combined.empty:
    data_to_write = [df_combined.columns.tolist()] + df_combined.values.tolist()
    daily_ws.update(values=data_to_write, range_name="A1")
    print(f"🎉 デイリーシートの更新が完了しました！ (合計: {len(df_combined)}件のタスク)")
else:
    print("今日のタスクはありません。")
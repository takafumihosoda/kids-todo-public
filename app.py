import streamlit as st
import gspread
import pandas as pd
import datetime
import json
import requests

st.set_page_config(page_title="キッズToDo", page_icon="🎈", layout="centered")
st.markdown("""
<style>
.block-container { padding-top: 1.5rem !important; padding-left: 0.8rem !important; padding-right: 0.8rem !important; }
h1 { font-size: 20px !important; padding-bottom: 5px !important; }
h3 { font-size: 16px !important; color: #444444 !important; padding-top: 10px !important; margin-bottom: 0px !important; }
div[data-testid="stCheckbox"] p { font-size: 14px !important; line-height: 1.5 !important; }
.stDataEditor { width: 100% !important; }
</style>
""", unsafe_allow_html=True)

jst = datetime.timezone(datetime.timedelta(hours=9))
now = datetime.datetime.now(jst)
today_str_check = f"{now.month}月{now.day}日"

# URLから誰が開いているかを判定
query_params = st.query_params
user_mode = query_params.get("name", "all") 

# 「20時以降」かつ「親が見ている時」だけ夜モードにする
if now.hour >= 20 and user_mode == "all":
    target_date = now + datetime.timedelta(days=1)
    mode_text = "🌙 明日のベース仕込みモード（夜20時〜24時）"
    is_night_mode = True
else:
    target_date = now
    mode_text = "🌞 当日の最終確認・配信モード" if user_mode == "all" else "🏃‍♀️ 今日も一日がんばろう！"
    is_night_mode = False

weekday_list = ["日", "月", "火", "水", "木", "金", "土"]
target_weekday_short = weekday_list[(target_date.weekday() + 1) % 7]
date_str = f"{target_date.month}月{target_date.day}日"

st.title(f"🎈 {date_str}({target_weekday_short}) のToDo")
st.caption(f"現在の状態：{mode_text}")

creds_dict = json.loads(st.secrets["gcp_credentials"])
gc = gspread.service_account_from_dict(creds_dict)
spreadsheet = gc.open('勉強ToDoデータベース')
daily_ws = spreadsheet.worksheet('デイリー')
prepaid_ws = spreadsheet.worksheet('翌日仕込み')

def send_line_message(text, target_id):
    if "line_channel_access_token" not in st.secrets:
        return False
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {st.secrets['line_channel_access_token']}"
    }
    payload = {
        "to": target_id,
        "messages": [{"type": "text", "text": text}]
    }
    response = requests.post(url, headers=headers, json=payload)
    return response.status_code == 200

def update_status(row_index, current_status):
    sheet_row = row_index + 2
    new_status = "完了" if current_status == "未完了" else "未完了"
    new_time = datetime.datetime.now(jst).strftime("%Y-%m-%d %H:%M:%S") if new_status == "完了" else ""
    # F列(6番目)がステータス、G列(7番目)が完了時間
    daily_ws.update_cell(sheet_row, 6, new_status)
    daily_ws.update_cell(sheet_row, 7, new_time)

def show_tasks(target_name, current_df):
    df_target = current_df[current_df["対象者"] == target_name].copy()
    if not df_target.empty:
        order_map = {"朝活": 0, "自習": 1, "SAPIX": 2, "ゆづき先生": 3, "おじいちゃん": 4}
        df_target["sort_key"] = df_target["タイミング"].map(order_map).fillna(99)
        df_target = df_target.sort_values("sort_key")

        total_tasks = len(df_target)
        completed_tasks = len(df_target[df_target["ステータス"] == "完了"])
        st.progress(completed_tasks / total_tasks)
        st.write(f"**進み具合: {completed_tasks} / {total_tasks}**")
        
        if total_tasks > 0 and completed_tasks == total_tasks:
            st.success("🎉 全部終わったね！素晴らしい！！")
            st.balloons()

        for index, row in df_target.iterrows():
            timing_str = f"【{row['タイミング']}】 " if row['タイミング'] else ""
            task_name = f"{timing_str}{row['タスク名']} （{row.get('メモ_所要時間目安_min', '')}分）"
            is_checked = row["ステータス"] == "完了"
            display_name = f"~~{task_name}~~" if is_checked else task_name
            
            if st.checkbox(display_name, value=is_checked, key=f"{target_name}_{index}") != is_checked:
                update_status(index, row["ステータス"])
                st.rerun()
    else:
        st.info("🎉 今日のタスクはありません！")

# ==========================================
# データの読み込み処理（ここをより強固にしました）
# ==========================================
prepaid_records = prepaid_ws.get_all_records()
df_prepaid_raw = pd.DataFrame(prepaid_records)
last_confirmed_date = str(df_prepaid_raw.iloc[0]["前回確定日"]) if not df_prepaid_raw.empty and "前回確定日" in df_prepaid_raw.columns else "なし"

# ★鉄のルール：子供たちの画面（および親画面のプレビュー）は、常に絶対にデイリーシートを見る
df_children_df = pd.DataFrame(daily_ws.get_all_records()) 

if is_night_mode:
    # 🌙 親の夜モード：「前回確定日」を隠して翌日仕込みシートを表示
    df_display = df_prepaid_raw.drop(columns=["前回確定日"], errors="ignore") if not df_prepaid_raw.empty else pd.DataFrame()
else:
    # 🌞 親の朝モード
    if last_confirmed_date == today_str_check:
        df_display = df_children_df.copy()
    else:
        # 朝の未確定時のみ、デイリーの未完了＋翌日仕込みを合体させる
        df_daily = df_children_df.copy()
        
        if not df_daily.empty and "ステータス" in df_daily.columns:
            df_leftover = df_daily[df_daily["ステータス"] == "未完了"].copy()
            g_col_name = df_leftover.columns[6] if len(df_leftover.columns) >= 7 else None
            if g_col_name:
                df_leftover[g_col_name] = ""
        else:
            df_leftover = pd.DataFrame()
            
        df_base = df_prepaid_raw.drop(columns=["前回確定日"], errors="ignore") if not df_prepaid_raw.empty else pd.DataFrame()
        if not df_base.empty:
            df_base["ステータス"] = "未完了"
            g_col_name = df_base.columns[6] if len(df_base.columns) >= 7 else None
            if g_col_name:
                df_base[g_col_name] = ""
            
        df_display = pd.concat([df_leftover, df_base], ignore_index=True)

# ==========================================
# 画面の表示
# ==========================================
if user_mode == "shiho":
    st.subheader("👧 栞帆ちゃんの専用ページ")
    show_tasks("栞帆", df_children_df)
elif user_mode == "yuka":
    st.subheader("👧 結楓ちゃんの専用ページ")
    show_tasks("結楓", df_children_df)
else:
    st.write("👨‍💻 **パパママ用 管理・編集画面**")
    
    if is_night_mode:
        st.info("🌙 夜間仕込み：ここで翌日のベースを修正・保存します。（今日の子供たちの画面には影響しません）")
    else:
        if last_confirmed_date == today_str_check:
            st.success("✨ 本日のToDoは確定・配信済みです。子供たちのリアルタイム進捗が下に表示されます。")
        else:
            st.warning("🚨 【前日の積み残し】＋【夜の仕込み】が自動合体したプリセットです。確認・修正して必ず下の確定ボタンを押してください。")
        
    edited_df = st.data_editor(df_display, num_rows="dynamic", key="data_editor", height=280)
    
    if st.button("🔄 編集内容を確定してスプレッドシートに保存する", type="primary", use_container_width=True):
        if is_night_mode:
            headers = edited_df.columns.values.tolist()
            values = edited_df.fillna("").values.tolist()
            extended_headers = headers + ["前回確定日"]
            extended_values = []
            for i, val in enumerate(values):
                extended_values.append(val + [last_confirmed_date] if i == 0 else val + [""])
            if not extended_values:
                extended_values = [[""] * len(headers) + [last_confirmed_date]]
            prepaid_ws.clear()
            prepaid_ws.update([extended_headers] + extended_values)
            st.success("明日のベースタスクとして『翌日仕込み』シートに保存しました！")
        else:
            save_df = edited_df.drop(columns=["前回確定日"], errors="ignore")
            daily_ws.clear()
            daily_ws.update([save_df.columns.values.tolist()] + save_df.fillna("").values.tolist())
            # J2セル（10列目）に今日の日付を刻印
            prepaid_ws.update_cell(2, 10, today_str_check)
            st.success("本日のToDoリストを確定・保存しました！子供たちへ配信可能です。")
        st.rerun()
        
    st.divider()
    
    st.write("📢 **子供たちへの配信（4人全員グループ宛）**")
    if st.button("🚀 栞帆・結楓に今日のToDoを配信する", type="secondary", use_container_width=True):
        if not is_night_mode and last_confirmed_date != today_str_check:
            st.error("先に上の『確定してスプレッドシートに保存する』ボタンを押してデータを確定させてください。")
        else:
            msg = f"⏰ 今日のToDoリストが届いたよ🎈\n\n👧 栞帆ちゃんはこちら👇\nhttps://kids-todo-public-jbseharpyqrnsqpdwfneg7.streamlit.app/?name=shiho\n\n👧 結楓ちゃんはこちら👇\nhttps://kids-todo-public-jbseharpyqrnsqpdwfneg7.streamlit.app/?name=yuka"
            if send_line_message(msg, st.secrets["line_group_family"]):
                st.success("家族全員のグループLINE宛にToDoリストを送信しました！🚀")

    st.divider()
    
    tab_shiho, tab_yuka = st.tabs(["👧 栞帆の進捗", "👧 結楓の進捗"])
    with tab_shiho:
        show_tasks("栞帆", df_children_df)
    with tab_yuka:
        show_tasks("結楓", df_children_df)

import streamlit as st
import gspread
import pandas as pd
import datetime
import json
import requests

# 1. 画面の基本設定とデザイン（スマホでも見やすいように最適化）
st.set_page_config(page_title="キッズToDo", page_icon="🎈", layout="centered")
st.markdown("""
<style>
.block-container { padding-top: 1.5rem !important; padding-left: 0.8rem !important; padding-right: 0.8rem !important; }
h1 { font-size: 20px !important; padding-bottom: 5px !important; }
h3 { font-size: 16px !important; color: #444444 !important; padding-top: 10px !important; margin-bottom: 0px !important; }
div[data-testid="stCheckbox"] p { font-size: 14px !important; line-height: 1.5 !important; }
/* スマホの横揺れ防止 */
.stDataEditor { width: 100% !important; }
</style>
""", unsafe_allow_html=True)

jst = datetime.timezone(datetime.timedelta(hours=9))
now = datetime.datetime.now(jst)
weekday_list = ["日", "月", "火", "水", "木", "金", "土"]
today_weekday_short = weekday_list[(now.weekday() + 1) % 7]
today_str = f"{now.month}月{now.day}日"

st.title(f"🎈 {today_str}({today_weekday_short}) のToDo")

query_params = st.query_params
user_mode = query_params.get("name", "all") 

# Streamlitの安全金庫からパスワードを読み込み
creds_dict = json.loads(st.secrets["gcp_credentials"])
gc = gspread.service_account_from_dict(creds_dict)

# LINE送信用の関数
def send_line_message(text, target_id):
    if "line_channel_access_token" not in st.secrets:
        st.error("LINEのトークンが設定されていません。")
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

# スプレッドシートデータの読み込み
spreadsheet = gc.open('勉強ToDoデータベース')
daily_ws = spreadsheet.worksheet('デイリー')
records = daily_ws.get_all_records()
df = pd.DataFrame(records)

def update_status(row_index, current_status):
    sheet_row = row_index + 2
    new_status = "完了" if current_status == "未完了" else "未完了"
    new_time = datetime.datetime.now(jst).strftime("%Y-%m-%d %H:%M:%S") if new_status == "完了" else ""
    daily_ws.update_cell(sheet_row, 6, new_status)
    daily_ws.update_cell(sheet_row, 7, new_time)

def show_tasks(target_name):
    df_target = df[df["対象者"] == target_name].copy()
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
            task_name = f"{timing_str}{row['タスク名']} （{row['メモ_所要時間目安_min']}分）"
            is_checked = row["ステータス"] == "完了"
            display_name = f"~~{task_name}~~" if is_checked else task_name
            
            if st.checkbox(display_name, value=is_checked, key=f"{target_name}_{index}") != is_checked:
                update_status(index, row["ステータス"])
                st.rerun()
    else:
        st.info("🎉 今日のタスクはありません！のんびり過ごそう！")

if df.empty:
    st.warning("デイリーシートにデータがありません。")
else:
    if user_mode == "shiho":
        st.subheader("👧 栞帆ちゃんの専用ページ")
        show_tasks("栞帆")
    elif user_mode == "yuka":
        st.subheader("👧 結楓ちゃんの専用ページ")
        show_tasks("結楓")
    else:
        st.write("👨‍💻 **パパママ用 管理・編集画面**")
        
        # 👑 直接編集エディタ
        st.caption("👇 タスクの修正・追加・削除ができます（スマホでもタップで編集可）")
        edited_df = st.data_editor(df, num_rows="dynamic", key="data_editor", height=250)
        
        if st.button("🔄 編集内容をスプレッドシートに保存する", type="secondary", use_container_width=True):
            daily_ws.clear()
            daily_ws.update([edited_df.columns.values.tolist()] + edited_df.fillna("").values.tolist())
            st.success("変更をスプレッドシートに保存しました！")
            st.rerun()
            
        st.divider()
        
        # 👑 LINE送信ボタン（1つだけに集約！）
        st.write("📢 **子供たちへの配信**")
        if st.button("🚀 栞帆・結楓にToDo通知を送る", type="primary", use_container_width=True):
            msg = f"⏰ 今日のToDoリスト🎈\n\n👧 栞帆ちゃんはこちら👇\nhttps://kids-todo-public-jbseharpyqrnsqpdwfneg7.streamlit.app/?name=shiho\n\n👧 結楓ちゃんはこちら👇\nhttps://kids-todo-public-jbseharpyqrnsqpdwfneg7.streamlit.app/?name=yuka"
            
            # 4人全員のグループID（line_group_family）へ直接送信！
            if send_line_message(msg, st.secrets["line_group_family"]):
                st.success("家族全員のグループLINE宛にToDoリストを送信しました！🚀")

        st.divider()
        
        tab_shiho, tab_yuka = st.tabs(["👧 栞帆のタスク", "👧 結楓のタスク"])
        with tab_shiho:
            show_tasks("栞帆")
        with tab_yuka:
            show_tasks("結楓")
import gspread
import pandas as pd
import datetime
import os
import json

def main():
    creds_json = os.environ.get("GCP_CREDENTIALS")
    if not creds_json:
        print("Error: GCP_CREDENTIALS not found.")
        return
        
    creds_dict = json.loads(creds_json)
    gc = gspread.service_account_from_dict(creds_dict)
    
    spreadsheet = gc.open('勉強ToDoデータベース')
    master_ws = spreadsheet.worksheet('マスター')
    prepaid_ws = spreadsheet.worksheet('翌日仕込み')
    
    jst = datetime.timezone(datetime.timedelta(hours=9))
    now = datetime.datetime.now(jst)
    today_str = f"{now.month}月{now.day}日"
    tomorrow = now + datetime.timedelta(days=1)
    
    # 🌟 J2セル（前回確定日）を直接読み取る
    last_confirmed = ""
    try:
        val = prepaid_ws.acell('J2').value
        if val:
            last_confirmed = str(val)
    except Exception as e:
        print("前回確定日の取得をスキップ:", e)

    # 🌟 現在の「翌日仕込み」シートのデータを取得しておく（未配信タスクの救出用）
    existing_records = prepaid_ws.get_all_records()
    df_existing = pd.DataFrame(existing_records)
    if not df_existing.empty and '前回確定日' in df_existing.columns:
        df_existing = df_existing.drop(columns=['前回確定日'])
        
    weekday_map = ["月", "火", "水", "木", "金", "土", "日"]
    tomorrow_weekday = weekday_map[tomorrow.weekday()]
    print(f"明日の日付: {tomorrow.month}月{tomorrow.day}日 ({tomorrow_weekday}曜日)")
    
    master_records = master_ws.get_all_records()
    df_master = pd.DataFrame(master_records)
    
    if df_master.empty:
        print("マスターシートが空です。")
        return
        
    # 明日の曜日に該当するタスクを抽出
    df_tomorrow_tasks = df_master[df_master['曜日'].str.contains(tomorrow_weekday, na=False)].copy()
    
    if 'ステータス' in df_tomorrow_tasks.columns:
        df_tomorrow_tasks['ステータス'] = '未完了'
    if len(df_tomorrow_tasks.columns) >= 7:
        g_col_name = df_tomorrow_tasks.columns[6]
        df_tomorrow_tasks[g_col_name] = ''
        
    # 🌟【最重要ロジック】パパが今日確定ボタンを押したかチェック
    if last_confirmed == today_str:
        # 今日すでに配信済みなら、安心して明日のタスクで上書き
        df_save = df_tomorrow_tasks
        print("今日の配信は完了しています。明日のタスクで上書きします。")
    else:
        # 今日配信していない（スキップした）なら、既存のタスクに明日のタスクを「合体」させる！
        print(f"今日の配信が未完了です！（前回確定日: {last_confirmed} / 今日: {today_str}）")
        print("未配信のタスクを残したまま、明日のタスクを追加します。")
        if not df_existing.empty:
            df_save = pd.concat([df_existing, df_tomorrow_tasks], ignore_index=True)
        else:
            df_save = df_tomorrow_tasks
            
    # シートを一度まっさらにする
    prepaid_ws.clear()
    
    # 合体したタスクを書き込む
    if df_save.empty:
         prepaid_ws.update([df_master.columns.values.tolist()])
    else:
         prepaid_ws.update([df_save.columns.values.tolist()] + df_save.fillna("").values.tolist())
         
    # J1とJ2セルに記憶を書き戻す
    prepaid_ws.update_cell(1, 10, "前回確定日")
    prepaid_ws.update_cell(2, 10, last_confirmed)
    
    print(f"翌日仕込みシートへの書き込み完了！ (記憶: {last_confirmed})")

if __name__ == '__main__':
    main()

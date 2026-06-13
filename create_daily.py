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
    
    # 🌟【追加】シートをリセットする前に「前回確定日」の記憶を救出する
    last_confirmed = ""
    try:
        existing_records = prepaid_ws.get_all_records()
        if len(existing_records) > 0 and "前回確定日" in existing_records[0]:
            last_confirmed = str(existing_records[0]["前回確定日"])
    except Exception as e:
        print("前回確定日の取得をスキップしました:", e)
    
    jst = datetime.timezone(datetime.timedelta(hours=9))
    now = datetime.datetime.now(jst)
    tomorrow = now + datetime.timedelta(days=1)
    
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
    
    # 必要な列を維持したままステータスをリセット
    df_save = df_tomorrow_tasks.copy()
    if 'ステータス' in df_save.columns:
        df_save['ステータス'] = '未完了'
        
    # G列（ステータス_最終更新）を空にする
    if len(df_save.columns) >= 7:
        g_col_name = df_save.columns[6]
        df_save[g_col_name] = ''
        
    # 🌟【修正】空っぽにするのではなく、さっき救出した記憶を引き継ぐ！
    df_save['前回確定日'] = last_confirmed
    
    prepaid_ws.clear()
    prepaid_ws.update([df_save.columns.values.tolist()] + df_save.fillna("").values.tolist())
    print("翌日仕込みシートへの明日のベースタスク書き込みが完了しました！")

if __name__ == '__main__':
    main()

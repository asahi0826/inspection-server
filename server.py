#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検査予定表 サーバー
起動方法: python server.py
アクセス: http://[このPCのIPアドレス]:8080
"""

import json
import os
import csv
import io
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from urllib.parse import urlparse, parse_qs

DATA_FILE = "data.json"

DEFAULT_MEMBERS = ['志田拓真', '笹原一興', '白幡　桂', '難波　啓', '矢口輝昌', '櫻井亮輔', '佐藤尚貴', '志田正嵩', '榎本主磨', '渡部駿介', '荒瀬　匠', '難波明治', '松浦 史', '金内颯太', '平藤孝幸', '蛸井滉太', '小林優太', '渡部海斗', '林　洸南', '小林　ライ', '渡部敦貴', '宮崎涼雅', '亀井誠一', '渡部　賢', '佐藤克也', '渡會恭平', '飯鉢航大', '宮本可奈子', '清和真伍', '佐藤由紀子', '佐藤大地']

# PostgreSQL接続（DATABASE_URL環境変数があれば使用）
DATABASE_URL = os.environ.get("DATABASE_URL")
pg_conn = None

def get_pg_conn():
    global pg_conn
    if DATABASE_URL:
        try:
            import psycopg2
            if pg_conn is None or pg_conn.closed:
                pg_conn = psycopg2.connect(DATABASE_URL, sslmode="require")
                pg_conn.autocommit = True
                # テーブル作成
                with pg_conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS appdata (
                            key TEXT PRIMARY KEY,
                            value TEXT
                        )
                    """)
            return pg_conn
        except Exception as e:
            print(f"[DB接続エラー] {e}")
    return None

def get_default_data():
    return {"members": DEFAULT_MEMBERS, "schedule": {}, "date": datetime.now().strftime("%Y-%m-%d")}

def load_data():
    conn = get_pg_conn()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT value FROM appdata WHERE key = 'main'")
                row = cur.fetchone()
                if row:
                    data = json.loads(row[0])
                    if "members" not in data:
                        data["members"] = DEFAULT_MEMBERS
                    # 日付が変わっていたら自動リセット
                    today = datetime.now().strftime("%Y-%m-%d")
                    last_date = data.get("date", today)
                    if last_date != today:
                        blue_count = 0
                        yellow_count = 0
                        schedule = data.get("schedule", {})
                        for member in schedule:
                            for time in schedule[member]:
                                for entry in schedule[member][time]:
                                    if isinstance(entry, dict):
                                        if entry.get("allowed"):
                                            blue_count += 1
                                        else:
                                            yellow_count += 1
                                    else:
                                        blue_count += 1
                        if blue_count > 0 or yellow_count > 0:
                            data["yesterday"] = {"blue": blue_count, "yellow": yellow_count}
                        data["schedule"] = {}
                        data["completed"] = {}
                        data["pending"] = {}
                        data["accept"] = {}
                        data["date"] = today
                        save_data(data)
                        print(f"[自動リセット] {last_date} → {today} 青{blue_count}件 黄{yellow_count}件")
                    return data
                else:
                    d = get_default_data()
                    save_data(d)
                    return d
        except Exception as e:
            print(f"[DB読込エラー] {e}")
    # fallback: ファイル
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "members" not in data:
            data["members"] = DEFAULT_MEMBERS
        today = datetime.now().strftime("%Y-%m-%d")
        last_date = data.get("date", today)
        if last_date != today:
            blue_count = 0
            yellow_count = 0
            schedule = data.get("schedule", {})
            for member in schedule:
                for time in schedule[member]:
                    for entry in schedule[member][time]:
                        if isinstance(entry, dict):
                            if entry.get("allowed"):
                                blue_count += 1
                            else:
                                yellow_count += 1
                        else:
                            blue_count += 1
            if blue_count > 0 or yellow_count > 0:
                data["yesterday"] = {"blue": blue_count, "yellow": yellow_count}
            data["schedule"] = {}
            data["completed"] = {}
            data["pending"] = {}
            data["accept"] = {}
            data["date"] = today
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"[自動リセット] 日付が変わりました（{last_date} → {today}）")
        return data
    return get_default_data()

def save_data(data):
    conn = get_pg_conn()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO appdata (key, value) VALUES ('main', %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                    (json.dumps(data, ensure_ascii=False),)
                )
            return
        except Exception as e:
            print(f"[DB保存エラー] {e}")
    # fallback: ファイル
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

db = load_data()

TIMES = ['8時〜9時','9時〜10時','10時〜11時','11時〜12時',
         '13時〜14時','14時〜15時','15時〜16時','16時〜17時','17時以降']

class Handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]} {args[1]}")

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, html):
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def send_csv(self, csv_text):
        body = ("\ufeff" + csv_text).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        today = datetime.now().strftime("%Y-%m-%d")
        self.send_header("Content-Disposition", f'attachment; filename="inspection_{today}.csv"')
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length else {}

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self.send_html(get_html())

        elif path == "/api/data":
            # アクセス時に日付チェックして自動リセット
            today = datetime.now().strftime("%Y-%m-%d")
            if db.get("date") and db["date"] != today:
                blue_count = 0
                yellow_count = 0
                schedule = db.get("schedule", {})
                for member in schedule:
                    for t in schedule[member]:
                        for entry in schedule[member][t]:
                            if isinstance(entry, dict):
                                if entry.get("allowed"):
                                    blue_count += 1
                                else:
                                    yellow_count += 1
                            else:
                                blue_count += 1
                if blue_count > 0 or yellow_count > 0:
                    db["yesterday"] = {"blue": blue_count, "yellow": yellow_count}
                db["schedule"] = {}
                db["completed"] = {}
                db["pending"] = {}
                db["accept"] = {}
                db["date"] = today
                save_data(db)
            self.send_json(db)

        elif path == "/api/csv":
            members = db.get("members", [])
            schedule = db.get("schedule", {})
            rows = [["担当者"] + TIMES]
            for m in members:
                row = [m]
                for t in TIMES:
                    entries = schedule.get(m, {}).get(t, [])
                    row.append(" / ".join(entries))
                rows.append(row)
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerows(rows)
            self.send_csv(output.getvalue())

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = self.read_body()

        if path == "/api/register":
            member = body.get("member", "").strip()
            time = body.get("time", "").strip()
            item = body.get("item", "").strip()
            content = body.get("content", "").strip()

            number = body.get("number", "").strip()

            if not member or not time or not number:
                self.send_json({"ok": False, "error": "必須項目が不足しています"}, 400)
                return
            exact_time = body.get("exactTime", "").strip()
            parts = []
            if number:
                parts.append(f"[{number}]")
            if exact_time:
                parts.append(f"({exact_time})")
            if item:
                parts.append(item)
            if content:
                parts.append(f"：{content}")
            text = " ".join(parts)

            # 入力時刻を記録
            now = datetime.now()
            total_min = now.hour * 60 + now.minute
            in_allowed = (480 <= total_min < 540) or (660 <= total_min < 720)
            entry = {"text": text, "allowed": in_allowed}

            if "schedule" not in db:
                db["schedule"] = {}
            if member not in db["schedule"]:
                db["schedule"][member] = {}
            if time not in db["schedule"][member]:
                db["schedule"][member][time] = []
            db["schedule"][member][time].append(entry)
            db["date"] = datetime.now().strftime("%Y-%m-%d")
            save_data(db)
            self.send_json({"ok": True})

        elif path == "/api/members/add":
            name = body.get("name", "").strip()
            if not name:
                self.send_json({"ok": False, "error": "名前が空です"}, 400)
                return
            if name in db["members"]:
                self.send_json({"ok": False, "error": "すでに存在します"}, 400)
                return
            db["members"].append(name)
            if "schedule" not in db:
                db["schedule"] = {}
            db["schedule"][name] = {}
            save_data(db)
            self.send_json({"ok": True})

        elif path == "/api/members/delete":
            name = body.get("name", "").strip()
            if name in db["members"]:
                db["members"].remove(name)
                db.get("schedule", {}).pop(name, None)
                save_data(db)
            self.send_json({"ok": True})

        elif path == "/api/entry/delete":
            member = body.get("member", "")
            time = body.get("time", "")
            idx = body.get("idx", -1)
            try:
                db["schedule"][member][time].pop(int(idx))
                if "completed" not in db:
                    db["completed"] = {}
                key = f"{member}__{time}"
                if key in db["completed"] and int(idx) < len(db["completed"][key]):
                    db["completed"][key].pop(int(idx))
                if "pending" not in db:
                    db["pending"] = {}
                if key in db["pending"] and int(idx) < len(db["pending"][key]):
                    db["pending"][key].pop(int(idx))
                save_data(db)
                self.send_json({"ok": True})
            except Exception as e:
                self.send_json({"ok": False, "error": str(e)}, 400)

        elif path == "/api/entry/complete":
            member = body.get("member", "")
            time = body.get("time", "")
            idx = body.get("idx", -1)
            try:
                if "completed" not in db:
                    db["completed"] = {}
                key = f"{member}__{time}"
                entries_count = len(db["schedule"][member][time])
                if key not in db["completed"]:
                    db["completed"][key] = [False] * entries_count
                while len(db["completed"][key]) < entries_count:
                    db["completed"][key].append(False)
                db["completed"][key][idx] = not db["completed"][key][idx]
                save_data(db)
                self.send_json({"ok": True, "completed": db["completed"][key][idx]})
            except Exception as e:
                self.send_json({"ok": False, "error": str(e)}, 400)

        elif path == "/api/entry/pending":
            member = body.get("member", "")
            time = body.get("time", "")
            idx = body.get("idx", -1)
            try:
                if "pending" not in db:
                    db["pending"] = {}
                key = f"{member}__{time}"
                entries_count = len(db["schedule"][member][time])
                if key not in db["pending"]:
                    db["pending"][key] = [False] * entries_count
                while len(db["pending"][key]) < entries_count:
                    db["pending"][key].append(False)
                db["pending"][key][idx] = not db["pending"][key][idx]
                save_data(db)
                self.send_json({"ok": True, "pending": db["pending"][key][idx]})
            except Exception as e:
                self.send_json({"ok": False, "error": str(e)}, 400)

        elif path == "/api/entry/accept":
            member = body.get("member", "")
            time = body.get("time", "")
            idx = body.get("idx", -1)
            try:
                if "accept" not in db:
                    db["accept"] = {}
                key = f"{member}__{time}"
                entries_count = len(db["schedule"][member][time])
                if key not in db["accept"]:
                    db["accept"][key] = [False] * entries_count
                while len(db["accept"][key]) < entries_count:
                    db["accept"][key].append(False)
                db["accept"][key][idx] = not db["accept"][key][idx]
                save_data(db)
                self.send_json({"ok": True, "accept": db["accept"][key][idx]})
            except Exception as e:
                self.send_json({"ok": False, "error": str(e)}, 400)

        elif path == "/api/reset":
            # リセット前に昨日の集計を保存
            blue_count = 0
            yellow_count = 0
            schedule = db.get("schedule", {})
            for member in schedule:
                for time in schedule[member]:
                    for entry in schedule[member][time]:
                        if isinstance(entry, dict):
                            if entry.get("allowed"):
                                blue_count += 1
                            else:
                                yellow_count += 1
                        else:
                            blue_count += 1
            if blue_count > 0 or yellow_count > 0:
                db["yesterday"] = {"blue": blue_count, "yellow": yellow_count}
            db["schedule"] = {}
            db["completed"] = {}
            db["pending"] = {}
            db["accept"] = {}
            save_data(db)
            self.send_json({"ok": True})

        else:
            self.send_response(404)
            self.end_headers()


def get_html():
    return '''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>検査予定表</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@300;400;500;700&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #1a1e2e;
    --surface: #222640;
    --surface2: #2a2f48;
    --border: #2e3247;
    --accent: #4f8ef7;
    --accent2: #38d9a9;
    --danger: #ff6b6b;
    --text: #e8eaf0;
    --text2: #8b90a7;
    --text3: #555a72;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: "Noto Sans JP", sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }
  body::before {
    content: ""; position: fixed; inset: 0;
    background-image: linear-gradient(var(--border) 1px, transparent 1px), linear-gradient(90deg, var(--border) 1px, transparent 1px);
    background-size: 40px 40px; opacity: 0.2; pointer-events: none; z-index: 0;
  }
  .app { position: relative; z-index: 1; max-width: 1200px; margin: 0 auto; padding: 28px 20px; }
  .header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; flex-wrap: wrap; gap: 12px; }
  .header-left h1 { font-size: 20px; font-weight: 700; }
  .header-left h1 span { color: #ffffff; }
  .header-left p { font-size: 11px; color: var(--text3); font-family: "DM Mono", monospace; margin-top: 3px; }
  .header-right { display: flex; align-items: center; gap: 10px; }
  .clock { font-family: "DM Mono", monospace; font-size: 20px; font-weight: 500; }
  .status-pill { display: inline-flex; align-items: center; gap: 5px; padding: 4px 10px; border-radius: 20px; font-size: 11px; font-weight: 500; }
  .status-pill.allowed { background: rgba(56,217,169,0.15); color: var(--accent2); border: 1px solid rgba(56,217,169,0.3); }
  .status-pill.denied { background: rgba(255,107,107,0.15); color: var(--danger); border: 1px solid rgba(255,107,107,0.3); }
  .dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; animation: pulse 2s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }
  .tabs { display: flex; gap: 4px; margin-bottom: 20px; background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 4px; width: 100%; flex-wrap: wrap; }
  .tab { padding: 7px 18px; border-radius: 7px; font-size: 12px; font-weight: 500; cursor: pointer; border: none; background: transparent; color: var(--text2); transition: all 0.2s; font-family: "Noto Sans JP", sans-serif; flex: 1; text-align: center; white-space: nowrap; }
  .tab.active { background: var(--accent); color: #fff; }
  .panel { display: none; }
  .panel.active { display: block; }
  .form-card, .members-card { background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 24px; }
  .form-label { font-size: 11px; color: var(--text3); letter-spacing: 0.1em; text-transform: uppercase; font-family: "DM Mono", monospace; margin-bottom: 18px; }
  .form-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 14px; margin-bottom: 14px; }
  .form-group { display: flex; flex-direction: column; gap: 6px; }
  .form-group.full { grid-column: 1/-1; }
  label { font-size: 11px; font-weight: 500; color: var(--text2); display: flex; align-items: center; gap: 4px; }
  .req { color: var(--danger); font-size: 10px; }
  select, input, textarea { background: var(--surface2); border: 1px solid var(--border); border-radius: 8px; padding: 9px 12px; font-size: 13px; font-family: "Noto Sans JP", sans-serif; color: var(--text); width: 100%; outline: none; transition: border-color 0.2s, box-shadow 0.2s; }
  select { appearance: none; background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%238b90a7' d='M6 8L1 3h10z'/%3E%3C/svg%3E"); background-repeat: no-repeat; background-position: right 12px center; cursor: pointer; }
  select:focus, input:focus, textarea:focus { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(79,142,247,0.12); }
  input::placeholder, textarea::placeholder { color: var(--text3); }
  textarea { resize: vertical; min-height: 70px; }
  .btn-row { display: flex; gap: 10px; margin-top: 4px; }
  .btn { padding: 10px 22px; border-radius: 8px; font-size: 13px; font-weight: 700; font-family: "Noto Sans JP", sans-serif; cursor: pointer; border: none; transition: all 0.2s; }
  .btn-primary { background: var(--accent); color: #fff; flex: 1; }
  .btn-primary:hover { background: #6ba3ff; transform: translateY(-1px); box-shadow: 0 4px 16px rgba(79,142,247,0.35); }
  .btn-outline { background: transparent; color: var(--accent2); border: 1px solid rgba(56,217,169,0.4); }
  .btn-outline:hover { background: rgba(56,217,169,0.08); }
  .btn-danger-outline { background: transparent; color: var(--danger); border: 1px solid rgba(255,107,107,0.4); padding: 6px 14px; font-size: 12px; }
  .btn-danger-outline:hover { background: rgba(255,107,107,0.08); }
  .btn-warn { background: transparent; color: var(--danger); border: 1px solid rgba(255,107,107,0.4); font-size: 12px; }
  .btn-warn:hover { background: rgba(255,107,107,0.08); }
  .table-toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; flex-wrap: wrap; gap: 10px; }
  .table-toolbar-title { font-size: 11px; color: var(--text3); font-family: "DM Mono", monospace; letter-spacing: 0.1em; }
  .table-wrap { overflow-x: auto; border-radius: 12px; border: 1px solid var(--border); }
  table { border-collapse: collapse; width: 100%; min-width: 700px; }
  th { background: var(--surface); padding: 10px 14px; font-size: 11px; font-weight: 600; color: var(--text2); border: 1px solid var(--border); white-space: nowrap; font-family: "DM Mono", monospace; letter-spacing: 0.04em; }
  th.name-col { background: #1e2235; color: var(--accent); min-width: 90px; position: sticky; left: 0; z-index: 2; }
  td { border: 1px solid var(--border); padding: 0; vertical-align: top; min-width: 110px; }
  td.name-cell { background: #1e2235; padding: 10px 12px; font-size: 12px; font-weight: 600; color: var(--text); position: sticky; left: 0; z-index: 1; white-space: nowrap; }
  td.data-cell { background: var(--surface); cursor: pointer; transition: background 0.15s; }
  td.data-cell:hover { background: #242840; }
  .cell-inner { padding: 6px 8px; min-height: 48px; display: flex; flex-direction: column; gap: 3px; }
  .entry-tag { background: rgba(79,142,247,0.15); border: 1px solid rgba(79,142,247,0.3); border-radius: 4px; padding: 5px 7px; font-size: 11px; color: #a8c5ff; display: flex; flex-direction: column; gap: 2px; line-height: 1.4; }
  .entry-tag.done { background: rgba(56,217,169,0.15); border-color: rgba(56,217,169,0.4); color: #38d9a9; opacity: 0.75; }
  .entry-tag.yellow { background: rgba(255,214,0,0.2); border-color: rgba(255,190,0,0.5); color: #b8860b; }
  .entry-tag.green { background: rgba(56,217,169,0.15); border-color: rgba(56,217,169,0.4); color: #20a87a; }
  .entry-tag.pending { background: rgba(180,180,180,0.15); border-color: rgba(180,180,180,0.4); color: #aaaaaa; opacity: 0.8; }
  .entry-tag.pending .entry-text { text-decoration: line-through; opacity: 0.6; }
  .pending-badge { font-size: 10px; color: #aaaaaa; margin-left: 2px; }
  .pending-btn { background: none; border: 1px solid rgba(180,180,180,0.4); color: #aaaaaa; cursor: pointer; font-size: 10px; padding: 1px 5px; border-radius: 3px; flex-shrink: 0; }
  .pending-btn:hover { background: rgba(180,180,180,0.15); }
  .entry-tag.green.done { background: rgba(56,217,169,0.3); border-color: rgba(56,217,169,0.6); color: #38d9a9; }
  .name-cell.green-member { background: rgba(56,217,169,0.1); border-left: 3px solid #38d9a9; }
  .entry-tag.yellow.done { background: rgba(56,217,169,0.15); border-color: rgba(56,217,169,0.4); color: #38d9a9; }
  .entry-tag.done .entry-text { text-decoration: line-through; opacity: 0.7; }
  .complete-btn { background: none; border: 1px solid rgba(79,142,247,0.4); color: #a8c5ff; cursor: pointer; font-size: 10px; padding: 1px 5px; border-radius: 3px; flex-shrink: 0; white-space: nowrap; }
  .complete-btn:hover { background: rgba(79,142,247,0.2); }
  .entry-tag.done .complete-btn { border-color: rgba(56,217,169,0.4); color: #38d9a9; }
  .entry-tag .del-btn { background: none; border: none; color: var(--danger); cursor: pointer; font-size: 11px; padding: 0 2px; opacity: 0.6; flex-shrink: 0; }
  .entry-tag .del-btn:hover { opacity: 1; }
  .empty-cell { opacity: 0.2; font-size: 18px; padding: 12px; color: var(--text3); }
  .overtime-header { background: rgba(255,80,80,0.85) !important; color: white !important; }
  .overtime-cell { background: rgba(255,80,80,0.08); border-color: rgba(255,80,80,0.3) !important; }
  .members-list { display: flex; flex-direction: column; gap: 8px; margin-bottom: 20px; }
  .member-row { display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; background: var(--surface2); border: 1px solid var(--border); border-radius: 8px; }
  .member-name { font-size: 13px; font-weight: 500; }
  .add-member-row { display: flex; gap: 10px; margin-top: 4px; }
  .add-member-row input { flex: 1; }
  .toast { position: fixed; bottom: 28px; left: 50%; transform: translateX(-50%) translateY(80px); background: var(--surface2); border: 1px solid var(--border); border-radius: 10px; padding: 11px 18px; font-size: 13px; display: flex; align-items: center; gap: 8px; transition: transform 0.3s cubic-bezier(0.34,1.56,0.64,1); z-index: 100; white-space: nowrap; }
  .toast.show { transform: translateX(-50%) translateY(0); }
  .toast.success { border-color: rgba(56,217,169,0.4); }
  .toast.error { border-color: rgba(255,107,107,0.4); }
  .empty-state { text-align: center; padding: 48px; color: var(--text3); font-size: 13px; }
  @media(max-width:600px){ .form-grid { grid-template-columns: 1fr 1fr; } }
</style>
</head>
<body>
<div class="app">
  <div class="header">
    <div class="header-left">
      <h1>検査<span>予定表</span></h1>
      <p>INSPECTION SCHEDULE SYSTEM</p>
    </div>
    <div class="header-right">
      <div class="clock" id="clock">--:--:--</div>
      <div class="status-pill allowed" id="statusPill">
        <div class="dot"></div>
        <span id="statusText">接続中</span>
      </div>
    </div>
  </div>

  <div class="tabs">
    <button class="tab active" onclick="switchTab(\'input\')">📝 入力</button>
    <button class="tab" onclick="switchTab(\'table\')">📊 予定表</button>
    <button class="tab" onclick="switchTab(\'members\')">👤 担当者管理</button>
  </div>

  <!-- 入力パネル -->
  <div class="panel active" id="panel-input">
    <div class="form-card">
      <div class="form-label">// 検査情報入力</div>
      <div class="form-grid">
        <div class="form-group">
          <label>担当者 <span class="req">必須</span></label>
          <select id="inpMember"><option value="">-- 選択 --</option></select>
        </div>
        <div class="form-group">
          <label>時間帯 <span class="req">必須</span></label>
          <select id="inpTime" onchange="onTimeChange()">
            <option value="">-- 選択 --</option>
            <option>8時〜9時</option><option>9時〜10時</option>
            <option>10時〜11時</option><option>11時〜12時</option>
            <option>13時〜14時</option><option>14時〜15時</option>
            <option>15時〜16時</option><option>16時〜17時</option>
            <option>17時以降</option>
          </select>
        </div>
        <div class="form-group">
          <label>管理番号 <span class="req">必須</span></label>
          <input type="text" id="inpNumber" placeholder="例）A-001" oninput="this.value=this.value.toUpperCase()">
        </div>
        <div class="form-group">
          <label>検査項目</label>
          <select id="inpItem">
            <option value="">-- 選択 --</option>
            <option>部分検査</option><option>1面目</option>
            <option>2面目</option><option>抜取り検査</option><option>その他</option>
          </select>
        </div>
        <div class="form-group" id="exactTimeGroup" style="display:none;">
          <label>開始時刻 <span class="req" id="exactTimeReq">必須</span></label>
          <input type="time" id="inpExactTime">
        </div>
        <div class="form-group full">
          <label>検査内容 <span class="req" id="contentReq" style="display:none;">必須</span></label>
          <textarea id="inpContent" placeholder="検査の詳細内容を入力してください..."></textarea>
        </div>
      </div>
      <div class="btn-row">
        <button class="btn btn-primary" onclick="register()">登録する</button>
        <button class="btn btn-outline" onclick="switchTab(\'table\')">予定表を見る →</button>
      </div>
    </div>
  </div>

  <!-- 予定表パネル -->
  <div class="panel" id="panel-table">
    <div class="table-toolbar">
      <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap;">
        <div class="table-toolbar-title">// 本日の検査予定表</div>
        <div id="yesterdayStats" style="display:none;gap:8px;align-items:center;font-size:11px;font-family:'DM Mono',monospace;">
          <span style="color:#8b90a7">昨日：</span>
          <span style="background:rgba(79,142,247,0.2);border:1px solid rgba(79,142,247,0.4);border-radius:4px;padding:2px 8px;color:#a8c5ff;">🔵 <span id="blueCount">0</span>件</span>
          <span style="background:rgba(255,214,0,0.2);border:1px solid rgba(255,190,0,0.4);border-radius:4px;padding:2px 8px;color:#b8860b;">🟡 <span id="yellowCount">0</span>件</span>
        </div>
      </div>
      <div style="display:flex;gap:8px">
        <button class="btn btn-warn" id="resetBtn" onclick="confirmReset()">🗑 リセット</button>
      </div>
    </div>
    <div class="table-wrap">
      <table id="scheduleTable"></table>
    </div>
  </div>

  <!-- 担当者管理パネル -->
  <div class="panel" id="panel-members">
    <div class="members-card">
      <div class="form-label" style="margin-bottom:16px">// 担当者一覧</div>
      <div class="members-list" id="membersList"></div>
      <div class="add-member-row">
        <input type="text" id="newMemberInput" placeholder="担当者名を入力...">
        <button class="btn btn-outline" onclick="addMember()">追加</button>
      </div>
    </div>
  </div>
</div>

<div class="toast" id="toast">
  <span id="toastIcon"></span>
  <span id="toastMsg"></span>
</div>

<script>
  const TIMES = ["8時〜9時","9時〜10時","10時〜11時","11時〜12時","13時〜14時","14時〜15時","15時〜16時","16時〜17時","17時以降"];
  const GREEN_MEMBERS = ["亀井誠一", "渡部\u3000賢", "佐藤克也", "渡會恭平", "飯鉢航大", "宮本可奈子", "清和真伍", "佐藤由紀子", "佐藤大地"];
  let db = { members: [], schedule: {} };

  async function api(method, path, body) {
    const res = await fetch(path, {
      method,
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined
    });
    return res.json().catch(() => ({}));
  }

  async function loadData() {
    db = await api("GET", "/api/data");
    renderMemberSelect();
  }

  // Clock
  function updateClock() {
    const now = new Date();
    document.getElementById("clock").textContent =
      [now.getHours(), now.getMinutes(), now.getSeconds()]
      .map(v => String(v).padStart(2,"0")).join(":");
  }
  setInterval(updateClock, 1000);
  updateClock();

  // Tab
  function switchTab(tab) {
    document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    document.getElementById("panel-" + tab).classList.add("active");
    const tabs = ["input","table","members"];
    document.querySelectorAll(".tab")[tabs.indexOf(tab)].classList.add("active");
    if (tab === "table") renderTable();
    if (tab === "members") renderMembers();
  }

  // Register
  function onTimeChange() {
    const time = document.getElementById("inpTime").value;
    const exactTimeGroup = document.getElementById("exactTimeGroup");
    const contentReq = document.getElementById("contentReq");
    if (time === "17時以降") {
      exactTimeGroup.style.display = "flex";
      contentReq.style.display = "inline";
    } else {
      exactTimeGroup.style.display = "none";
      contentReq.style.display = "none";
      document.getElementById("inpExactTime").value = "";
    }
  }

  async function register() {
    const member = document.getElementById("inpMember").value;
    const time = document.getElementById("inpTime").value;
    const number = document.getElementById("inpNumber").value.trim();
    const item = document.getElementById("inpItem").value;
    const content = document.getElementById("inpContent").value.trim();
    const exactTime = document.getElementById("inpExactTime").value.trim();
    if (!member || !time || !number) { showToast("担当者・時間帯・管理番号は必須です", "error"); return; }
    if (time === "17時以降" && !exactTime) { showToast("17時以降の場合は開始時刻を入力してください", "error"); return; }
    if (time === "17時以降" && !content) { showToast("17時以降の場合は検査内容を入力してください", "error"); return; }
    if (time === "17時以降") {
      if (!confirm("📞 検査課にTELしてください！ 登録を続けますか？")) return;
    }
    const res = await api("POST", "/api/register", { member, time, item, number, content, exactTime });
    if (res.ok) {
      await loadData();
      document.getElementById("inpNumber").value = "";
      document.getElementById("inpTime").value = "";
      document.getElementById("inpItem").value = "";
      document.getElementById("inpContent").value = "";
      document.getElementById("inpExactTime").value = "";
      document.getElementById("exactTimeGroup").style.display = "none";
      document.getElementById("contentReq").style.display = "none";
      showToast(member + " / " + time + " に登録しました", "success");
    } else {
      showToast(res.error || "エラーが発生しました", "error");
    }
  }

  // Table
  function renderTable() {
    const table = document.getElementById("scheduleTable");
    const members = db.members || [];
    const schedule = db.schedule || {};
    if (members.length === 0) {
      table.innerHTML = "<tr><td class=\'empty-state\' colspan=\'10\'>担当者を登録してください</td></tr>";
      return;
    }
    const completed = db.completed || {};
    const pending = db.pending || {};
    // 入力がある担当者だけ表示・緑グループは下に
    const hasEntry = m => TIMES.some(t => schedule[m] && schedule[m][t] && schedule[m][t].length > 0);
    const activeBlue = members.filter(m => hasEntry(m) && !GREEN_MEMBERS.includes(m));
    const activeGreen = members.filter(m => hasEntry(m) && GREEN_MEMBERS.includes(m));
    const activeMembers = [...activeBlue, ...activeGreen];
    const activeTimes = {};
    TIMES.forEach(t => {
      activeTimes[t] = activeMembers.some(m => schedule[m] && schedule[m][t] && schedule[m][t].length > 0);
    });
    let html = "<thead><tr><th class=\'name-col\'>担当者</th>";
    TIMES.forEach(t => {
      const narrow = !activeTimes[t] ? " style=\'width:36px;min-width:36px;max-width:36px;font-size:9px;padding:4px 2px;\'" : "";
      const shortLabel = activeTimes[t] ? t : t.replace("時〜","〜").replace(/時$/,"");
      if (t === "17時以降") {
        html += "<th class=\'overtime-header\'" + narrow + ">" + (activeTimes[t] ? t : "17↓") + "</th>";
      } else {
        html += "<th" + narrow + ">" + shortLabel + "</th>";
      }
    });
    html += "</tr></thead><tbody>";
    if (activeMembers.length === 0) {
      table.innerHTML = "<tr><td class=\'empty-state\' colspan=\'10\'>まだ入力がありません</td></tr>";
      return;
    }
    activeMembers.forEach(m => {
      const nameCellClass = GREEN_MEMBERS.includes(m) ? "name-cell green-member" : "name-cell";
      html += "<tr><td class=\'" + nameCellClass + "\'>" + m + "</td>";
      TIMES.forEach((t, ti) => {
        const entries = (schedule[m] && schedule[m][t]) ? schedule[m][t] : [];
        const key = m + "__" + t;
        const doneList = completed[key] || [];
        const pendingList = pending[key] || [];
        const acceptList = (db.accept && db.accept[key]) || [];
        const overtimeClass = t === "17時以降" ? " overtime-cell" : "";
        const narrowCell = !activeTimes[t] ? " style=\'width:36px;min-width:36px;max-width:36px;padding:2px;\'" : "";
        html += "<td class=\'data-cell" + overtimeClass + "\'" + narrowCell + "><div class=\'cell-inner\'>";
        if (entries.length === 0) {
          html += "<div class=\'empty-cell\'>+</div>";
        } else {
          entries.forEach((e, idx) => {
            const isDone = doneList[idx] === true;
            const isPending = false; // disabled
            const text = (typeof e === "object") ? e.text : e;
            const isYellow = (typeof e === "object") ? !e.allowed : false;
            const stateClass = isDone ? " done" : (isYellow ? " yellow" : "");
            const btnLabel = isDone ? "✓ 完了" : "完了";
            const pendingLabel = isPending ? "⚪ 保留中" : "";
            html += "<div class=\'entry-tag" + stateClass + "\'>" +
              "<div class=\'entry-text\'>" + text + "</div>" +
              "<div style=\'display:flex;gap:3px;margin-top:4px;\'>" +
              "<button class=\'complete-btn\' onclick=\'toggleComplete(" + JSON.stringify(m) + "," + JSON.stringify(t) + "," + idx + ")\'>"+btnLabel+"</button>" +
              "<button class=\'complete-btn\' onclick=\'toggleAccept(" + JSON.stringify(m) + "," + JSON.stringify(t) + "," + idx + ")\'>" + (acceptList[idx] ? "✓ 受入" : "受入") + "</button>" +
              "<button class=\'del-btn\' onclick=\'deleteEntry(" + JSON.stringify(m) + "," + JSON.stringify(t) + "," + idx + ")\'>✕</button>" +
              "</div></div>";
          });
        }
        html += "</div></td>";
      });
      html += "</tr>";
    });
    html += "</tbody>";
    table.innerHTML = html;
  }

  async function toggleComplete(member, time, idx) {
    const res = await api("POST", "/api/entry/complete", { member, time, idx });
    if (res.ok) { await loadData(); renderTable(); }
  }

  async function togglePending(member, time, idx) {
    const res = await api("POST", "/api/entry/pending", { member, time, idx });
    if (res.ok) { await loadData(); renderTable(); }
  }

  async function toggleAccept(member, time, idx) {
    const res = await api("POST", "/api/entry/accept", { member, time, idx });
    if (res.ok) { await loadData(); renderTable(); }
  }

  async function deleteEntry(member, time, idx) {
    if (time === "17時以降") {
      if (!confirm("📞 検査課にTELしてください！ 削除を続けますか？")) return;
    } else {
      if (!confirm("削除しますか？")) return;
    }
    const res = await api("POST", "/api/entry/delete", { member, time, idx });
    if (res.ok) { await loadData(); renderTable(); showToast("削除しました", "success"); }
  }

  let resetPending = false;
  let resetTimer = null;

  function confirmReset() {
    const btn = document.getElementById("resetBtn");
    if (!resetPending) {
      resetPending = true;
      btn.textContent = "本当に消す？";
      btn.style.background = "rgba(255,107,107,0.2)";
      resetTimer = setTimeout(() => {
        resetPending = false;
        btn.textContent = "🗑 リセット";
        btn.style.background = "";
      }, 3000);
    } else {
      clearTimeout(resetTimer);
      resetPending = false;
      btn.textContent = "🗑 リセット";
      btn.style.background = "";
      resetSchedule();
    }
  }

  async function resetSchedule() {
    const res = await api("POST", "/api/reset");
    if (res.ok) {
      await loadData();
      renderTable();
      updateYesterdayStats();
      showToast("リセットしました", "success");
    }
  }

  function updateYesterdayStats() {
    const yesterday = db.yesterday;
    if (yesterday && (yesterday.blue > 0 || yesterday.yellow > 0)) {
      document.getElementById("yesterdayStats").style.display = "flex";
      document.getElementById("blueCount").textContent = yesterday.blue;
      document.getElementById("yellowCount").textContent = yesterday.yellow;
    } else {
      document.getElementById("yesterdayStats").style.display = "none";
    }
  }

  // Members
  function renderMembers() {
    const list = document.getElementById("membersList");
    const members = db.members || [];
    if (members.length === 0) { list.innerHTML = "<div class=\'empty-state\'>担当者が登録されていません</div>"; return; }
    list.innerHTML = members.map(m =>
      "<div class=\'member-row\'><div class=\'member-name\'>" + m + "</div>" +
      "<button class=\'btn btn-danger-outline\' onclick=\'deleteMember(" + JSON.stringify(m) + ")\'>削除</button></div>"
    ).join("");
  }

  async function addMember() {
    const input = document.getElementById("newMemberInput");
    const name = input.value.trim();
    if (!name) { showToast("名前を入力してください", "error"); return; }
    const res = await api("POST", "/api/members/add", { name });
    if (res.ok) { input.value = ""; await loadData(); renderMembers(); showToast(name + " を追加しました", "success"); }
    else showToast(res.error || "エラー", "error");
  }

  async function deleteMember(name) {
    if (!confirm("「" + name + "」を削除しますか？\\n登録済みのデータも消えます。")) return;
    const res = await api("POST", "/api/members/delete", { name });
    if (res.ok) { await loadData(); renderMembers(); showToast(name + " を削除しました", "success"); }
  }

  function renderMemberSelect() {
    const sel = document.getElementById("inpMember");
    const current = sel.value;
    sel.innerHTML = "<option value=\\'\\'>-- 選択 --</option>";
    (db.members || []).forEach(m => {
      const opt = document.createElement("option");
      opt.value = m; opt.textContent = m;
      if (m === current) opt.selected = true;
      sel.appendChild(opt);
    });
  }

  // Toast
  function showToast(msg, type) {
    type = type || "success";
    const t = document.getElementById("toast");
    document.getElementById("toastIcon").textContent = type === "success" ? "✅" : "❌";
    document.getElementById("toastMsg").textContent = msg;
    t.className = "toast " + type + " show";
    setTimeout(() => { t.className = "toast " + type; }, 2800);
  }

  // 5秒ごとに自動更新
  setInterval(async () => {
    await loadData();
    updateYesterdayStats();
    const activePanel = document.querySelector('.panel.active');
    if (activePanel && activePanel.id === 'panel-table') {
      renderTable();
    }
  }, 5000);

  loadData().then(() => { if(typeof updateYesterdayStats === "function") updateYesterdayStats(); });
</script>
</body>
</html>'''


def get_local_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "localhost"


if __name__ == "__main__":
    ip = get_local_ip()
    port = 8080
    print("=" * 50)
    print("  検査予定表サーバー 起動中...")
    print("=" * 50)
    print(f"  このPCからアクセス: http://localhost:{port}")
    print(f"  他のPCからアクセス: http://{ip}:{port}")
    print("=" * 50)
    print("  停止するには Ctrl + C を押してください")
    print("=" * 50)
    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()

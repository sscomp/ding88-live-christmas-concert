#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple registration server:
- Serves static files (index.html, images) from the current directory.
- POST /register accepts JSON, writes to SQLite with the required ticket fields.
- GET /admin shows a lightweight table of registrations.
"""

import base64
import json
import os
import random
import sqlite3
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse
import html


BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "registrations.db"
TZ = timezone(timedelta(hours=8))
ADMIN_USER = "admin"
ADMIN_PASS = "88888888"


SCHEMA = """
CREATE TABLE IF NOT EXISTS registrations (
    "票號" TEXT PRIMARY KEY,
    "狀態" TEXT,
    "訂購人姓名" TEXT,
    "訂購人Email" TEXT,
    "訂購人電話" TEXT,
    "參加人姓名" TEXT,
    "參加人Email" TEXT,
    "參加人電話" TEXT,
    "報名時間(GTM+8)" TEXT,
    "有效時間(GTM+8)" TEXT,
    "票種分組" TEXT,
    "票券名稱" TEXT,
    "票價(NT)" INTEGER,
    "付款時間(GTM+8)" TEXT,
    "付款方式" TEXT,
    "信用卡末四碼" TEXT,
    "首次驗票時間(GTM+8)" TEXT,
    "首次驗票備註" TEXT,
    "最後驗票時間(GTM+8)" TEXT,
    "最後驗票備註" TEXT,
    "驗票次數" INTEGER,
    "驗票通知" TEXT,
    "備註" TEXT,
    "取消原因" TEXT,
    "出生年月日" TEXT
);
"""


def ensure_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(SCHEMA)
        conn.commit()


def generate_ticket_number() -> str:
    now = datetime.now(TZ)
    return f"DING{now.strftime('%Y%m%d%H%M%S')}{random.randint(100, 999)}"


def validate_payload(payload: Dict[str, Any]) -> List[str]:
    required = ["attendee_name", "attendee_email", "attendee_phone", "ticket_type", "birth_date"]
    missing = []
    for key in required:
        value = payload.get(key, "")
        if not isinstance(value, str) or not value.strip():
            missing.append(key)
    return missing


def insert_registration(payload: Dict[str, Any]) -> str:
    ticket_number = generate_ticket_number()
    now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S GMT+8")
    buyer_name = payload["attendee_name"].strip()
    buyer_email = payload["attendee_email"].strip()
    buyer_phone = payload["attendee_phone"].strip()
    birth_date = payload["birth_date"].strip()
    ticket_type = payload["ticket_type"].strip() or "免費票 0 元"

    params = (
        ticket_number,               # 票號
        "已報名",                     # 狀態
        buyer_name,                  # 訂購人姓名
        buyer_email,                 # 訂購人Email
        buyer_phone,                 # 訂購人電話
        payload["attendee_name"].strip(),   # 參加人姓名
        payload["attendee_email"].strip(),  # 參加人Email
        payload["attendee_phone"].strip(),  # 參加人電話
        now,                         # 報名時間(GTM+8)
        "",                          # 有效時間(GTM+8)
        ticket_type,                 # 票種分組
        ticket_type,                 # 票券名稱
        0,                           # 票價(NT)
        "",                          # 付款時間(GTM+8)
        "免費票",                    # 付款方式
        "",                          # 信用卡末四碼
        "",                          # 首次驗票時間(GTM+8)
        "",                          # 首次驗票備註
        "",                          # 最後驗票時間(GTM+8)
        "",                          # 最後驗票備註
        0,                           # 驗票次數
        "",                          # 驗票通知
        "",                          # 備註
        "",                          # 取消原因
        birth_date                   # 出生年月日
    )

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO registrations (
                "票號","狀態","訂購人姓名","訂購人Email","訂購人電話",
                "參加人姓名","參加人Email","參加人電話","報名時間(GTM+8)",
                "有效時間(GTM+8)","票種分組","票券名稱","票價(NT)",
                "付款時間(GTM+8)","付款方式","信用卡末四碼",
                "首次驗票時間(GTM+8)","首次驗票備註","最後驗票時間(GTM+8)","最後驗票備註",
                "驗票次數","驗票通知","備註","取消原因","出生年月日"
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            params,
        )
        conn.commit()

    return ticket_number


def fetch_registrations() -> List[Dict[str, Any]]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            """
            SELECT
                "票號","狀態","參加人姓名","參加人Email","參加人電話",
                "票券名稱","票價(NT)","報名時間(GTM+8)","出生年月日",
                "首次驗票時間(GTM+8)","首次驗票備註",
                "最後驗票時間(GTM+8)","最後驗票備註","驗票次數"
            FROM registrations
            ORDER BY "報名時間(GTM+8)" DESC
            """
        )
        return [dict(row) for row in cur.fetchall()]


def verify_ticket(ticket_number: str, note: str) -> Dict[str, Any]:
    now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S GMT+8")
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            'SELECT * FROM registrations WHERE "票號" = ?',
            (ticket_number,),
        ).fetchone()
        if row is None:
            raise ValueError("查無此票號")

        first_time = row["首次驗票時間(GTM+8)"] or now
        first_note = row["首次驗票備註"] or note
        last_time = now
        last_note = note or row["最後驗票備註"] or ""
        count = (row["驗票次數"] or 0) + 1
        status = "已報名，已驗票"

        conn.execute(
            """
            UPDATE registrations
            SET "狀態"=?,
                "首次驗票時間(GTM+8)"=?,
                "首次驗票備註"=?,
                "最後驗票時間(GTM+8)"=?,
                "最後驗票備註"=?,
                "驗票次數"=?
            WHERE "票號"=?
            """,
            (status, first_time, first_note, last_time, last_note, count, ticket_number),
        )
        conn.commit()

    return {
        "ticket_number": ticket_number,
        "status": status,
        "last_verified_at": last_time,
        "last_note": last_note,
        "count": count,
    }


def delete_ticket(ticket_number: str) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            'SELECT 1 FROM registrations WHERE "票號" = ?',
            (ticket_number,),
        ).fetchone()
        if row is None:
            raise ValueError("查無此票號")
        conn.execute('DELETE FROM registrations WHERE "票號" = ?', (ticket_number,))
        conn.commit()


class RegistrationHandler(SimpleHTTPRequestHandler):
    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/register":
            self._handle_register()
            return
        if parsed.path == "/verify":
            if not self._require_basic_auth():
                return
            self._handle_verify()
            return
        if parsed.path == "/delete":
            if not self._require_basic_auth():
                return
            self._handle_delete()
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def _handle_register(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(HTTPStatus.LENGTH_REQUIRED, "Content-Length missing")
            return

        try:
            body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(body)
        except Exception:
            self._send_json({"ok": False, "error": "無法解析送出的資料。"}, status=HTTPStatus.BAD_REQUEST)
            return

        missing = validate_payload(payload)
        if missing:
            self._send_json(
                {"ok": False, "error": f"缺少必填欄位：{', '.join(missing)}"},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        try:
            ticket_number = insert_registration(payload)
        except sqlite3.IntegrityError:
            self._send_json({"ok": False, "error": "資料庫寫入失敗，請稍後再試。"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        except Exception as exc:  # noqa: BLE001
            self._send_json({"ok": False, "error": f"寫入時發生錯誤：{exc}"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        self._send_json({"ok": True, "ticket_number": ticket_number})

    def _handle_verify(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json({"ok": False, "error": "缺少 Content-Length"}, status=HTTPStatus.LENGTH_REQUIRED)
            return

        try:
            body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(body)
        except Exception:
            self._send_json({"ok": False, "error": "無法解析送出的資料。"}, status=HTTPStatus.BAD_REQUEST)
            return

        ticket_number = str(payload.get("ticket_number", "")).strip()
        note = str(payload.get("note", "")).strip()
        if not ticket_number:
            self._send_json({"ok": False, "error": "缺少票號"}, status=HTTPStatus.BAD_REQUEST)
            return

        try:
            result = verify_ticket(ticket_number, note)
        except ValueError as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.NOT_FOUND)
            return
        except Exception as exc:  # noqa: BLE001
            self._send_json({"ok": False, "error": f"驗票失敗：{exc}"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        self._send_json({"ok": True, **result})

    def _handle_delete(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json({"ok": False, "error": "缺少 Content-Length"}, status=HTTPStatus.LENGTH_REQUIRED)
            return

        try:
            body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(body)
        except Exception:
            self._send_json({"ok": False, "error": "無法解析送出的資料。"}, status=HTTPStatus.BAD_REQUEST)
            return

        ticket_number = str(payload.get("ticket_number", "")).strip()
        if not ticket_number:
            self._send_json({"ok": False, "error": "缺少票號"}, status=HTTPStatus.BAD_REQUEST)
            return

        try:
            delete_ticket(ticket_number)
        except ValueError as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.NOT_FOUND)
            return
        except Exception as exc:  # noqa: BLE001
            self._send_json({"ok": False, "error": f"刪除失敗：{exc}"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        self._send_json({"ok": True, "ticket_number": ticket_number})

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/admin":
            if not self._require_basic_auth():
                return
            self._render_admin()
            return
        super().do_GET()

    def _send_json(self, payload: Dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _require_basic_auth(self) -> bool:
        header = self.headers.get("Authorization", "")
        if header.startswith("Basic "):
            try:
                decoded = base64.b64decode(header.split(" ", 1)[1]).decode("utf-8")
                user, pwd = decoded.split(":", 1)
                if user == ADMIN_USER and pwd == ADMIN_PASS:
                    return True
            except Exception:
                pass
        self.send_response(HTTPStatus.UNAUTHORIZED)
        self.send_header("WWW-Authenticate", 'Basic realm="Admin", charset="UTF-8"')
        self.end_headers()
        return False

    def _render_admin(self) -> None:
        rows = fetch_registrations()
        html_rows = []
        for row in rows:
            def esc(value: Any) -> str:
                return html.escape(str(value)) if value is not None else ""

            cells = [
                f'<td class="actions"><button class="delete-btn" data-ticket="{esc(row.get("票號"))}">刪除</button></td>',
                f"<td>{esc(row.get('票號'))}</td>",
                f"<td>{esc(row.get('狀態'))}</td>",
                f"<td>{esc(row.get('參加人姓名'))}</td>",
                f"<td>{esc(row.get('參加人Email'))}</td>",
                f"<td>{esc(row.get('參加人電話'))}</td>",
                f"<td>{esc(row.get('票券名稱'))}</td>",
                f"<td>{esc(row.get('票價(NT)'))}</td>",
                f"<td>{esc(row.get('報名時間(GTM+8)'))}</td>",
                f"<td>{esc(row.get('出生年月日'))}</td>",
                f"<td>{esc(row.get('最後驗票時間(GTM+8)'))}</td>",
                f"<td>{esc(row.get('最後驗票備註'))}</td>",
                f"<td>{esc(row.get('驗票次數') or 0)}</td>",
                f'<td class="actions"><button class="verify-btn" data-ticket="{esc(row.get("票號"))}">驗票</button></td>',
            ]
            html_rows.append(f"<tr>{''.join(cells)}</tr>")

        body = f"""
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="UTF-8">
  <title>報名管理</title>
  <style>
    body {{ font-family: -apple-system,BlinkMacSystemFont,"Noto Sans TC","PingFang TC","Microsoft JhengHei",sans-serif; background:#0b0704; color:#f6e7c8; padding:20px; }}
    h1 {{ color:#f0c56a; }}
    table {{ width:100%; border-collapse: collapse; margin-top:16px; }}
    th, td {{ border:1px solid rgba(255,255,255,0.12); padding:10px; text-align:left; font-size:14px; }}
    th {{ background:rgba(240,197,106,0.12); color:#f0c56a; }}
    tr:nth-child(even) {{ background:rgba(255,255,255,0.02); }}
    a {{ color:#f0c56a; }}
    .verify-btn {{ background:#f0c56a; color:#23160b; border:1px solid rgba(240,197,106,0.6); border-radius:8px; padding:8px 12px; cursor:pointer; font-weight:600; }}
    .verify-btn:disabled {{ opacity:0.6; cursor:not-allowed; }}
    .delete-btn {{ background:#ff6b6b; color:#fff; border:1px solid rgba(255,107,107,0.7); border-radius:8px; padding:8px 12px; cursor:pointer; font-weight:600; }}
    .delete-btn:disabled {{ opacity:0.6; cursor:not-allowed; }}
    .actions {{ text-align:center; }}
  </style>
</head>
<body>
  <h1>報名管理</h1>
  <p>總筆數：{len(rows)}</p>
  <table>
    <thead>
      <tr>
        <th>刪除</th>
        <th>票號</th>
        <th>狀態</th>
        <th>參加人姓名</th>
        <th>參加人Email</th>
        <th>參加人電話</th>
        <th>票券名稱</th>
        <th>票價(NT)</th>
        <th>報名時間(GTM+8)</th>
        <th>出生年月日</th>
        <th>最後驗票時間</th>
        <th>最後驗票備註</th>
        <th>驗票次數</th>
        <th>操作</th>
      </tr>
    </thead>
    <tbody>
      {''.join(html_rows) if html_rows else '<tr><td colspan="14">目前沒有報名資料。</td></tr>'}
    </tbody>
  </table>
  <p><a href="/">返回報名頁</a></p>
  <script>
    document.querySelectorAll(".verify-btn").forEach((btn) => {{
      btn.addEventListener("click", async () => {{
        const ticket = btn.dataset.ticket;
        if (!ticket) return;
        const note = prompt("輸入驗票備註（可空白）") ?? "";
        btn.disabled = true;
        btn.textContent = "驗票中...";
        try {{
          const res = await fetch("/verify", {{
            method: "POST",
            headers: {{ "Content-Type": "application/json" }},
            credentials: "same-origin",
            body: JSON.stringify({{ ticket_number: ticket, note }}),
          }});
          const data = await res.json();
          if (!res.ok || !data.ok) {{
            throw new Error(data.error || "驗票失敗");
          }}
          alert(`驗票成功，票號：${{ticket}}\\n狀態：${{data.status}}\\n最後驗票時間：${{data.last_verified_at}}`);
          location.reload();
        }} catch (err) {{
          alert(err.message || "驗票失敗");
        }} finally {{
          btn.disabled = false;
          btn.textContent = "驗票";
        }}
      }});
    }});

    document.querySelectorAll(".delete-btn").forEach((btn) => {{
      btn.addEventListener("click", async () => {{
        const ticket = btn.dataset.ticket;
        if (!ticket) return;
        const confirmed = confirm(`確定刪除票號：${{ticket}} 嗎？此動作無法復原。`);
        if (!confirmed) return;
        btn.disabled = true;
        btn.textContent = "刪除中...";
        try {{
          const res = await fetch("/delete", {{
            method: "POST",
            headers: {{ "Content-Type": "application/json" }},
            credentials: "same-origin",
            body: JSON.stringify({{ ticket_number: ticket }}),
          }});
          const data = await res.json();
          if (!res.ok || !data.ok) {{
            throw new Error(data.error || "刪除失敗");
          }}
          alert(`票號 ${{ticket}} 已刪除。`);
          location.reload();
        }} catch (err) {{
          alert(err.message || "刪除失敗");
        }} finally {{
          btn.disabled = false;
          btn.textContent = "刪除";
        }}
      }});
    }});
  </script>
</body>
</html>
"""
        data = body.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def run() -> None:
    ensure_db()
    port = int(os.environ.get("PORT", "8000"))
    address = ("0.0.0.0", port)
    httpd = ThreadingHTTPServer(address, RegistrationHandler)
    print(f"Serving on http://{address[0]}:{address[1]} (Ctrl+C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    run()

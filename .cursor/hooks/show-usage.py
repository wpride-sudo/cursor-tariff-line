# -*- coding: utf-8 -*-
"""Print the Cursor plan usage percent for the agent window. Never prints tokens."""
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from datetime import date

STATE_DB = os.path.join(
    os.environ.get("APPDATA", ""),
    "Cursor",
    "User",
    "globalStorage",
    "state.vscdb",
)
USAGE_URL = "https://api2.cursor.sh/aiserver.v1.DashboardService/GetCurrentPeriodUsage"
LAST_USAGE_PATH = os.path.join(
    os.environ.get("USERPROFILE", ""),
    ".cursor",
    "hooks",
    "usage-last.json",
)


def fail(message):
    payload = {
        "continue": True,
        "additional_context": (
            "Процент тарифа сейчас недоступен ("
            + message
            + "). Первой строкой ответа в окне агента покажи только: н/д"
        ),
    }
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def read_access_token():
    uri = "file:" + STATE_DB.replace("\\", "/") + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=3)
    try:
        row = connection.execute(
            "SELECT value FROM ItemTable WHERE key = ?",
            ("cursorAuth/accessToken",),
        ).fetchone()
    finally:
        connection.close()
    if not row or not row[0]:
        raise RuntimeError("нет входа в Cursor")
    return row[0]


def fetch_usage(token):
    request = urllib.request.Request(
        USAGE_URL,
        data=b"{}",
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "Connect-Protocol-Version": "1",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def spent_percent(usage):
    plan = usage.get("planUsage") or {}
    total = plan.get("totalPercentUsed")
    if isinstance(total, (int, float)):
        return str(round(total)) + "%"
    limit = plan.get("limit") or 0
    included = plan.get("includedSpend")
    if included is None:
        included = plan.get("totalSpend") or 0
    if limit:
        value = round(included / limit * 100)
        if value < 0:
            value = 0
        return str(value) + "%"
    return "н/д"


def allowed_percent():
    day = date.today().day
    return str((day * 100) // 30) + "%"


def usage_line(spent):
    return "Allowed " + allowed_percent() + ", now " + spent


def read_last_usage():
    try:
        with open(LAST_USAGE_PATH, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def write_last_usage(spent_number, delta, changed_at):
    folder = os.path.dirname(LAST_USAGE_PATH)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(LAST_USAGE_PATH, "w", encoding="utf-8") as handle:
        json.dump(
            {"spent": spent_number, "delta": delta, "changed_at": changed_at},
            handle,
        )


def change_label(spent):
    if not spent.endswith("%"):
        return None
    try:
        current = int(spent[:-1])
    except ValueError:
        return None
    state = read_last_usage()
    previous = state.get("spent")
    now = time.time()
    delta = None
    if isinstance(previous, int) and current != previous:
        delta = current - previous
        write_last_usage(current, delta if delta > 0 else 0, now)
    elif not isinstance(previous, int):
        write_last_usage(current, 0, now)
    else:
        stored = state.get("delta")
        changed_at = state.get("changed_at") or 0
        if isinstance(stored, int) and stored > 0 and now - changed_at < 2:
            delta = stored
    if not isinstance(delta, int) or delta <= 0:
        return None
    return "+" + str(delta)


def line_tone(spent):
    try:
        allowed_n = int(allowed_percent()[:-1])
        spent_n = int(spent[:-1])
    except ValueError:
        return None
    if spent_n >= allowed_n:
        return "danger"
    return "success"


def main():
    try:
        token = read_access_token()
        usage = fetch_usage(token)
        spent = spent_percent(usage)
        label = usage_line(spent)
        tone = line_tone(spent)
        change = change_label(spent)
    except urllib.error.HTTPError as error:
        fail("ошибка " + str(error.code))
        return
    except Exception as error:
        fail(str(error))
        return

    if change and tone:
        context = (
            "Не используй span и не печатай эту строку чёрным текстом: в чате цвет сбрасывается. "
            "Процент вырос на "
            + change
            + ". Покажи в окне агента только цветную строку «"
            + label
            + "» через встроенную визуализацию, одним абзацем, без шкал, маленьким обычным шрифтом без жирного начертания, класс vis-text-small. "
            "Цвет текста: var(--"
            + tone
            + "). Зелёный success, если Now меньше Allowed. Красный danger, если Now равно Allowed или больше. "
            "Справа припиши красным var(--danger) разницу «"
            + change
            + "». В ответах без нового прироста эту строку не показывай."
        )
    else:
        context = "Строку расхода тарифа в этом ответе не показывай: прироста процента не было."
    payload = {
        "continue": True,
        "additional_context": context,
    }
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()

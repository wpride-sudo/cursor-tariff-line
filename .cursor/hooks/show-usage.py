# -*- coding: utf-8 -*-
"""Print the Cursor plan usage percent for the agent window. Never prints tokens."""
import calendar
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from datetime import date

USAGE_URL = "https://api2.cursor.sh/aiserver.v1.DashboardService/GetCurrentPeriodUsage"
DEFAULT_RESET_DAY = 27


def home_dir():
    return os.environ.get("USERPROFILE") or os.path.expanduser("~")


def cursor_user_dir():
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.join(home_dir(), "AppData", "Roaming")
        return os.path.join(base, "Cursor", "User")
    if sys.platform == "darwin":
        return os.path.join(home_dir(), "Library", "Application Support", "Cursor", "User")
    config_home = os.environ.get("XDG_CONFIG_HOME") or os.path.join(home_dir(), ".config")
    return os.path.join(config_home, "Cursor", "User")


def state_db_path():
    return os.path.join(cursor_user_dir(), "globalStorage", "state.vscdb")


def hooks_home():
    return os.path.join(home_dir(), ".cursor", "hooks")


LAST_USAGE_PATH = os.path.join(hooks_home(), "usage-last.json")
STATE_DB = state_db_path()


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


def read_reset_day():
    env_day = os.environ.get("CURSOR_USAGE_RESET_DAY")
    if env_day:
        try:
            day = int(env_day)
            if 1 <= day <= 31:
                return day
        except ValueError:
            pass
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"),
        os.path.join(hooks_home(), "config.json"),
    ]
    for path in candidates:
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
            day = int(data.get("resetDay"))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            continue
        if 1 <= day <= 31:
            return day
    return DEFAULT_RESET_DAY


def shift_month(year, month, step):
    month += step
    while month < 1:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return year, month


def reset_on(year, month):
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(read_reset_day(), last_day))


def allowed_percent(today=None):
    today = today or date.today()
    this_reset = reset_on(today.year, today.month)
    if today >= this_reset:
        start = this_reset
        year, month = shift_month(today.year, today.month, 1)
        end = reset_on(year, month)
    else:
        year, month = shift_month(today.year, today.month, -1)
        start = reset_on(year, month)
        end = this_reset
    period = (end - start).days
    if period <= 0:
        return "0%"
    elapsed = (today - start).days
    return str((elapsed * 100) // period) + "%"


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


def display_context(label, tone, change):
    text = (
        "Не используй span и не печатай эту строку чёрным текстом: в чате цвет сбрасывается. "
        "Покажи в окне агента только цветную строку «"
        + label
        + "» через встроенную визуализацию, одним абзацем, без шкал, маленьким обычным шрифтом без жирного начертания, класс vis-text-small. "
        "Цвет текста: var(--"
        + tone
        + "). Зелёный success, если Now меньше Allowed. Красный danger, если Now равно Allowed или больше."
    )
    if change:
        text += (
            " Процент вырос на "
            + change
            + ". Справа припиши красным var(--danger) разницу «"
            + change
            + "». В ответах без нового прироста эту строку не показывай."
        )
    else:
        text += " Пользователь запросил показ сейчас. Прироста не приписывай."
    return text


def main():
    force_show = "--show" in sys.argv
    try:
        token = read_access_token()
        usage = fetch_usage(token)
        spent = spent_percent(usage)
        label = usage_line(spent)
        tone = line_tone(spent)
        change = None if force_show else change_label(spent)
    except urllib.error.HTTPError as error:
        fail("ошибка " + str(error.code))
        return
    except Exception as error:
        fail(str(error))
        return

    if force_show and tone:
        context = display_context(label, tone, None)
    elif change and tone:
        context = display_context(label, tone, change)
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

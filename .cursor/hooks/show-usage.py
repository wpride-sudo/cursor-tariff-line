# -*- coding: utf-8 -*-
"""Print the Cursor plan usage percent for the agent window. Never prints tokens."""
import base64
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


TOKEN_KEYS = ("cursorAuth/accessToken", "cursorAuth/refreshToken")
SAFE_STORAGE_PREFIX = "cursor-safe-storage:v1:"


def read_auth_value(key):
    value = read_stored_value(key)
    if value and key in TOKEN_KEYS:
        return unwrap_token(value)
    return value


def read_stored_value(key):
    connection = sqlite3.connect(STATE_DB, timeout=5)
    try:
        row = connection.execute(
            "SELECT value FROM ItemTable WHERE key = ?",
            (key,),
        ).fetchone()
    finally:
        connection.close()
    if not row or not row[0]:
        return None
    value = row[0]
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    return value


def unwrap_token(value):
    if not value.startswith(SAFE_STORAGE_PREFIX):
        return value
    if sys.platform != "win32":
        raise RuntimeError("вход Cursor зашифрован, на этой системе его нельзя прочитать")
    raw = base64.b64decode(value[len(SAFE_STORAGE_PREFIX) :])
    plain = decrypt_secret_blob(raw).decode("utf-8")
    if plain.count(".") < 2:
        raise RuntimeError("не удалось расшифровать вход Cursor")
    return plain


def wrap_token(value):
    if sys.platform != "win32":
        return value
    key = cursor_encryption_key()
    nonce = os.urandom(12)
    sealed = aes_gcm_encrypt(key, nonce, value.encode("utf-8"))
    return SAFE_STORAGE_PREFIX + base64.b64encode(b"v10" + nonce + sealed).decode("ascii")


def decrypt_secret_blob(raw):
    if raw.startswith(b"v10"):
        if len(raw) < 3 + 12 + 16:
            raise RuntimeError("не удалось расшифровать вход Cursor")
        key = cursor_encryption_key()
        return aes_gcm_decrypt(key, raw[3:15], raw[15:])
    return _dpapi(raw, protect=False)


def cursor_encryption_key():
    root = os.path.dirname(cursor_user_dir())
    candidates = (
        os.path.join(root, "Local State"),
        os.path.join(cursor_user_dir(), "Local State"),
    )
    path = next((item for item in candidates if os.path.isfile(item)), None)
    if not path:
        raise RuntimeError("нет ключа шифрования Cursor")
    try:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
        encoded = payload["os_crypt"]["encrypted_key"]
    except (OSError, KeyError, json.JSONDecodeError):
        raise RuntimeError("нет ключа шифрования Cursor")
    raw = base64.b64decode(encoded)
    if raw.startswith(b"DPAPI"):
        raw = raw[5:]
    return _dpapi(raw, protect=False)


def aes_gcm_decrypt(key, nonce, cipher_and_tag):
    if len(cipher_and_tag) < 16:
        raise RuntimeError("не удалось расшифровать вход Cursor")
    return _aes_gcm(key, nonce, cipher_and_tag[:-16], cipher_and_tag[-16:], encrypt=False)


def aes_gcm_encrypt(key, nonce, plain):
    return _aes_gcm(key, nonce, plain, None, encrypt=True)


def _aes_gcm(key, nonce, data, tag, encrypt):
    import ctypes

    bcrypt = ctypes.WinDLL("bcrypt.dll")
    bcrypt.BCryptOpenAlgorithmProvider.argtypes = [
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_wchar_p,
        ctypes.c_wchar_p,
        ctypes.c_ulong,
    ]
    bcrypt.BCryptOpenAlgorithmProvider.restype = ctypes.c_long
    bcrypt.BCryptSetProperty.argtypes = [
        ctypes.c_void_p,
        ctypes.c_wchar_p,
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
    ]
    bcrypt.BCryptSetProperty.restype = ctypes.c_long
    bcrypt.BCryptGetProperty.argtypes = [
        ctypes.c_void_p,
        ctypes.c_wchar_p,
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.POINTER(ctypes.c_ulong),
        ctypes.c_ulong,
    ]
    bcrypt.BCryptGetProperty.restype = ctypes.c_long
    bcrypt.BCryptGenerateSymmetricKey.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
    ]
    bcrypt.BCryptGenerateSymmetricKey.restype = ctypes.c_long
    bcrypt.BCryptDecrypt.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.POINTER(ctypes.c_ulong),
        ctypes.c_ulong,
    ]
    bcrypt.BCryptDecrypt.restype = ctypes.c_long
    bcrypt.BCryptEncrypt.argtypes = bcrypt.BCryptDecrypt.argtypes
    bcrypt.BCryptEncrypt.restype = ctypes.c_long
    bcrypt.BCryptDestroyKey.argtypes = [ctypes.c_void_p]
    bcrypt.BCryptDestroyKey.restype = ctypes.c_long
    bcrypt.BCryptCloseAlgorithmProvider.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    bcrypt.BCryptCloseAlgorithmProvider.restype = ctypes.c_long
    alg = ctypes.c_void_p()
    key_handle = ctypes.c_void_p()
    status = bcrypt.BCryptOpenAlgorithmProvider(ctypes.byref(alg), "AES", None, 0)
    if status != 0:
        raise RuntimeError("не удалось расшифровать вход Cursor, aes " + hex(status & 0xFFFFFFFF))
    try:
        mode = ctypes.create_unicode_buffer("ChainingModeGCM")
        status = bcrypt.BCryptSetProperty(
            alg,
            "ChainingMode",
            ctypes.cast(mode, ctypes.c_void_p),
            ctypes.sizeof(mode),
            0,
        )
        if status != 0:
            raise RuntimeError("не удалось расшифровать вход Cursor, mode " + hex(status & 0xFFFFFFFF))
        obj_len = ctypes.c_ulong(0)
        written = ctypes.c_ulong(0)
        status = bcrypt.BCryptGetProperty(
            alg,
            "ObjectLength",
            ctypes.byref(obj_len),
            ctypes.sizeof(obj_len),
            ctypes.byref(written),
            0,
        )
        if status != 0:
            raise RuntimeError("не удалось расшифровать вход Cursor, obj " + hex(status & 0xFFFFFFFF))
        key_object = ctypes.create_string_buffer(obj_len.value)
        secret = ctypes.create_string_buffer(key, len(key))
        status = bcrypt.BCryptGenerateSymmetricKey(
            alg,
            ctypes.byref(key_handle),
            key_object,
            obj_len.value,
            secret,
            len(key),
            0,
        )
        if status != 0:
            raise RuntimeError("не удалось расшифровать вход Cursor, key " + hex(status & 0xFFFFFFFF))
        try:
            class AUTH(ctypes.Structure):
                _fields_ = [
                    ("cbSize", ctypes.c_ulong),
                    ("dwInfoVersion", ctypes.c_ulong),
                    ("pbNonce", ctypes.c_void_p),
                    ("cbNonce", ctypes.c_ulong),
                    ("pbAuthData", ctypes.c_void_p),
                    ("cbAuthData", ctypes.c_ulong),
                    ("pbTag", ctypes.c_void_p),
                    ("cbTag", ctypes.c_ulong),
                    ("pbMacContext", ctypes.c_void_p),
                    ("cbMacContext", ctypes.c_ulong),
                    ("cbAAD", ctypes.c_ulong),
                    ("cbData", ctypes.c_ulonglong),
                    ("dwFlags", ctypes.c_ulong),
                ]

            info = AUTH()
            info.cbSize = ctypes.sizeof(AUTH)
            info.dwInfoVersion = 1
            nonce_buf = ctypes.create_string_buffer(nonce, len(nonce))
            info.pbNonce = ctypes.cast(nonce_buf, ctypes.c_void_p)
            info.cbNonce = len(nonce)
            tag_buf = ctypes.create_string_buffer(16 if tag is None else tag, 16)
            info.pbTag = ctypes.cast(tag_buf, ctypes.c_void_p)
            info.cbTag = 16
            source = ctypes.create_string_buffer(data, len(data))
            output = ctypes.create_string_buffer(len(data))
            out_len = ctypes.c_ulong(0)
            function = bcrypt.BCryptEncrypt if encrypt else bcrypt.BCryptDecrypt
            status = function(
                key_handle,
                source,
                len(data),
                ctypes.byref(info),
                None,
                0,
                output,
                len(data),
                ctypes.byref(out_len),
                0,
            )
            if status != 0:
                raise RuntimeError("не удалось расшифровать вход Cursor, gcm " + hex(status & 0xFFFFFFFF))
            body = output.raw[: out_len.value]
            if encrypt:
                return body + tag_buf.raw[:16]
            return body
        finally:
            bcrypt.BCryptDestroyKey(key_handle)
    finally:
        bcrypt.BCryptCloseAlgorithmProvider(alg, 0)


def _dpapi(data, protect):
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    buffer = ctypes.create_string_buffer(data, len(data))
    blob_in = DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    blob_out = DATA_BLOB()
    function = ctypes.windll.crypt32.CryptProtectData if protect else ctypes.windll.crypt32.CryptUnprotectData
    ok = function(
        ctypes.byref(blob_in),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(blob_out),
    )
    if not ok:
        code = ctypes.GetLastError()
        raise RuntimeError("не удалось расшифровать вход Cursor, код " + str(code))
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def read_access_token():
    token = read_auth_value("cursorAuth/accessToken")
    if not token:
        raise RuntimeError("нет входа в Cursor")
    return token


def save_auth_value(key, value):
    if key in TOKEN_KEYS:
        current = read_stored_value(key)
        if current and current.startswith(SAFE_STORAGE_PREFIX):
            value = wrap_token(value)
    connection = sqlite3.connect(STATE_DB, timeout=5)
    try:
        connection.execute(
            "UPDATE ItemTable SET value = ? WHERE key = ?",
            (value, key),
        )
        if connection.total_changes == 0:
            connection.execute(
                "INSERT INTO ItemTable (key, value) VALUES (?, ?)",
                (key, value),
            )
        connection.commit()
    finally:
        connection.close()


def token_expired(token):
    parts = token.split(".")
    if len(parts) < 2:
        return False
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except (json.JSONDecodeError, ValueError):
        return False
    expires_at = claims.get("exp")
    if not isinstance(expires_at, (int, float)):
        return False
    return expires_at <= time.time() + 120


def refresh_access_token():
    refresh_token = read_auth_value("cursorAuth/refreshToken")
    if not refresh_token:
        raise RuntimeError("в базе нет токена обновления")
    body = json.dumps(
        {
            "grant_type": "refresh_token",
            "client_id": "KbZUR41cY7W6zRSdpSUJ7I7mLYBKOCmB",
            "refresh_token": refresh_token,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://api2.cursor.sh/oauth/token",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise RuntimeError("обновление входа, ошибка " + str(error.code)) from error
    token = payload.get("access_token") or payload.get("accessToken") or ""
    if payload.get("shouldLogout") or not token:
        raise RuntimeError("сессия сброшена, войдите в Cursor заново")
    try:
        save_auth_value("cursorAuth/accessToken", token)
        rotated = payload.get("refresh_token") or payload.get("refreshToken") or ""
        if rotated:
            save_auth_value("cursorAuth/refreshToken", rotated)
    except sqlite3.Error:
        pass
    return token


def request_usage(token):
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


def fetch_usage(token):
    if token_expired(token):
        token = refresh_access_token()
    try:
        return request_usage(token)
    except urllib.error.HTTPError as error:
        if error.code != 401:
            raise
        return request_usage(refresh_access_token())


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

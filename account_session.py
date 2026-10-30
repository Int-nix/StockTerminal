"""Read launcher session encrypted for the current Windows user (Windows only)."""
import base64
import ctypes
import json
import os
from ctypes import wintypes
from pathlib import Path


def _unprotect_dpapi(encoded):
    if os.name != "nt":
        return None

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

    raw = base64.b64decode(encoded, validate=True)
    source_buffer = ctypes.create_string_buffer(raw)
    source = DATA_BLOB(len(raw), ctypes.cast(source_buffer, ctypes.POINTER(ctypes.c_byte)))
    result = DATA_BLOB()
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    crypt32.CryptUnprotectData.argtypes = [ctypes.POINTER(DATA_BLOB), ctypes.c_void_p,
                                           ctypes.c_void_p, ctypes.c_void_p,
                                           ctypes.c_void_p, wintypes.DWORD,
                                           ctypes.POINTER(DATA_BLOB)]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    if not crypt32.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 0, ctypes.byref(result)):
        return None
    try:
        return ctypes.string_at(result.pbData, result.cbData).decode("utf-8")
    finally:
        ctypes.WinDLL("kernel32", use_last_error=True).LocalFree(ctypes.cast(result.pbData, ctypes.c_void_p))


def load_launcher_session():
    """Return {username, token, api_base}, or None if no valid local session exists."""
    if os.name != "nt":
        return None
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        return None
    path = Path(base) / "StockTerminal" / "data" / "account-session.json"
    try:
        saved = json.loads(path.read_text(encoding="utf-8-sig"))
        token = _unprotect_dpapi(saved["token_dpapi"])
        username = saved["username"]
        if not token or not isinstance(username, str) or not username.strip():
            return None
        return {"username": username, "token": token,
                "api_base": saved.get("api_base", "http://127.0.0.1:8000")}
    except (OSError, ValueError, KeyError, TypeError):
        return None

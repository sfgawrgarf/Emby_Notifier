#!/usr/bin/env python3
"""Create the notifier env file without printing or persisting plaintext elsewhere."""

import json
import os
import sqlite3
import tempfile
from pathlib import Path

from cryptography.fernet import Fernet


CMS_DB = Path("/root/cms/config/cms-online.db")
MHTI_DB = Path("/root/mhti/data/scraper.db")
MHTI_KEY = Path("/root/mhti/data/.secret_key")
TARGET = Path("/root/emby/.env.emby-notifier-wechat")
EMBY_ENV = Path("/root/emby/.env.embynotice")


def require_env_value(value, name):
    value = str(value or "")
    if not value or "\n" in value or "\r" in value:
        raise RuntimeError(f"{name} is missing or invalid")
    return value


def load_env(path):
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


with sqlite3.connect(CMS_DB) as conn:
    row = conn.execute(
        "SELECT config_json FROM cms_config WHERE key = ?", ("message",)
    ).fetchone()
if not row:
    raise RuntimeError("CMS message configuration was not found")

wechat = json.loads(row[0]).get("wechat", {})
if not wechat.get("WECHAT_STATUS"):
    raise RuntimeError("CMS WeChat configuration is not enabled")

with sqlite3.connect(MHTI_DB) as conn:
    row = conn.execute(
        "SELECT value, encrypted FROM config WHERE key = ?", ("tmdb_api_token",)
    ).fetchone()
if not row:
    raise RuntimeError("MHTI TMDB token was not found")

tmdb_token = row[0]
if row[1]:
    tmdb_token = Fernet(MHTI_KEY.read_bytes().strip()).decrypt(
        tmdb_token.encode("utf-8")
    ).decode("utf-8")

values = {
    "TZ": "Asia/Shanghai",
    "TMDB_API_TOKEN": require_env_value(tmdb_token, "TMDB_API_TOKEN"),
    "TMDB_IMAGE_DOMAIN": "https://image.tmdb.org",
    "EMBY_PUBLIC_URL": "https://avemby.aabbss.de",
    "EMBY_API_URL": "http://emby:8096",
    "EMBY_API_KEY": require_env_value(
        load_env(EMBY_ENV).get("EMBY_API_KEY"), "EMBY_API_KEY"
    ),
    "WECHAT_CORP_ID": require_env_value(wechat.get("WECHAT_COR_PID"), "WECHAT_CORP_ID"),
    "WECHAT_CORP_SECRET": require_env_value(
        wechat.get("WECHAT_APP_SECRET"), "WECHAT_CORP_SECRET"
    ),
    "WECHAT_AGENT_ID": require_env_value(
        wechat.get("WECHAT_APP_ID"), "WECHAT_AGENT_ID"
    ),
    "WECHAT_USER_ID": "@all",
    "WECHAT_MSG_TYPE": "news",
    "LOG_LEVEL": "INFO",
    "LOG_EXPORT": "False",
    "SEND_WELCOME": "False",
}

TARGET.parent.mkdir(parents=True, exist_ok=True)
fd, temp_path = tempfile.mkstemp(prefix=".emby-notifier-", dir=TARGET.parent)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")
    os.chmod(temp_path, 0o600)
    os.replace(temp_path, TARGET)
finally:
    if os.path.exists(temp_path):
        os.unlink(temp_path)

print(f"Created {TARGET} with mode {oct(TARGET.stat().st_mode & 0o777)}")

#!/usr/bin/env python3
"""Back up, switch, or restore the Emby webhook without exposing its API key."""

import argparse
import json
import os
import tempfile
import urllib.request
from pathlib import Path


ENV_FILE = Path("/root/emby/.env.embynotice")
API_BASE = "http://172.19.0.5:8096"
ADMIN_USER_ID = "b3da938dc3e94cc2a2f40c6c6b21bf25"
SETTING_URL = (
    f"{API_BASE}/Users/{ADMIN_USER_ID}/TypedSettings/usernotifications"
)
NEW_WEBHOOK_URL = "http://emby-notifier-wechat:8000/"


def load_env(path):
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def request_json(api_key, method="GET", payload=None):
    body = None if payload is None else json.dumps(
        payload, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    request = urllib.request.Request(
        SETTING_URL,
        data=body,
        method=method,
        headers={
            "X-Emby-Token": api_key,
            "Content-Type": "application/octet-stream",
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        data = response.read()
    return json.loads(data) if data else None


def write_private_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".emby-webhook-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.chmod(temp_path, 0o600)
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def describe(value):
    notification = next(
        item
        for item in value.get("Notifications", [])
        if item.get("NotifierKey") == "webhooknotifications"
    )
    return {
        "enabled": notification.get("Enabled"),
        "events": notification.get("EventIds"),
        "url": notification.get("Options", {}).get("Url"),
        "multipart": notification.get("Options", {}).get(
            "EnableMultipartFormData"
        ),
    }


parser = argparse.ArgumentParser()
parser.add_argument("action", choices=("backup", "switch", "restore", "show"))
parser.add_argument("--backup", type=Path, required=False)
args = parser.parse_args()

api_key = load_env(ENV_FILE).get("EMBY_API_KEY")
if not api_key:
    raise RuntimeError("EMBY_API_KEY was not found")

if args.action == "restore":
    if not args.backup:
        parser.error("--backup is required for restore")
    restored = json.loads(args.backup.read_text(encoding="utf-8"))
    request_json(api_key, "POST", restored)
    verified = request_json(api_key)
    if verified != restored:
        raise RuntimeError("Webhook restore verification failed")
    print(json.dumps(describe(verified), ensure_ascii=False))
else:
    current = request_json(api_key)
    if args.action == "backup":
        if not args.backup:
            parser.error("--backup is required for backup")
        write_private_json(args.backup, current)
        print(f"Backup created: {args.backup}")
    elif args.action == "switch":
        if args.backup:
            write_private_json(args.backup, current)
        updated = json.loads(json.dumps(current))
        notification = next(
            item
            for item in updated.get("Notifications", [])
            if item.get("NotifierKey") == "webhooknotifications"
        )
        notification["Enabled"] = True
        notification["EventIds"] = ["library.new"]
        notification.setdefault("Options", {})
        notification["Options"]["EnableMultipartFormData"] = "false"
        notification["Options"]["Url"] = NEW_WEBHOOK_URL
        request_json(api_key, "POST", updated)
        verified = request_json(api_key)
        if verified != updated:
            raise RuntimeError("Webhook switch verification failed")
        print(json.dumps(describe(verified), ensure_ascii=False))
    else:
        print(json.dumps(describe(current), ensure_ascii=False))

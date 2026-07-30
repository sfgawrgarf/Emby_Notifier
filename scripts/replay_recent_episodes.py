#!/usr/bin/env python3
"""Replay recent Emby episode additions through the current notifier."""

import argparse
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ENV_FILE = Path("/root/emby/.env.embynotice")
EMBY_API_BASE = "http://172.19.0.5:8096"


def load_env(path):
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def get_json(url, api_key):
    request = urllib.request.Request(url, headers={"X-Emby-Token": api_key})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read())


def parse_timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


parser = argparse.ArgumentParser()
parser.add_argument("--created-after", required=True)
parser.add_argument("--notifier-url", required=True)
parser.add_argument("--send", action="store_true")
args = parser.parse_args()

api_key = load_env(ENV_FILE).get("EMBY_API_KEY")
if not api_key:
    raise RuntimeError("EMBY_API_KEY was not found")

query = urllib.parse.urlencode(
    {
        "Recursive": "true",
        "IncludeItemTypes": "Episode",
        "SortBy": "DateCreated",
        "SortOrder": "Descending",
        "Limit": "100",
        "Fields": (
            "ProviderIds,PremiereDate,ProductionYear,Overview,"
            "CommunityRating,DateCreated"
        ),
    }
)
items = get_json(f"{EMBY_API_BASE}/Items?{query}", api_key).get("Items", [])
server = get_json(f"{EMBY_API_BASE}/System/Info", api_key)
cutoff = parse_timestamp(args.created_after)
recent = [
    item
    for item in items
    if item.get("DateCreated")
    and parse_timestamp(item["DateCreated"]) >= cutoff
]
recent.sort(key=lambda item: parse_timestamp(item["DateCreated"]))

print(f"Matched {len(recent)} recent episode(s):")
for item in recent:
    print(
        f"- {item.get('SeriesName')} "
        f"S{int(item.get('ParentIndexNumber') or 0):02d}"
        f"E{int(item.get('IndexNumber') or 0):02d} "
        f"id={item.get('Id')}"
    )

if not args.send:
    raise SystemExit(0)

for item in recent:
    item.setdefault(
        "PremiereDate",
        str(item.get("ProductionYear") or parse_timestamp(item["DateCreated"]).year),
    )
    item.setdefault("ProviderIds", {})
    event = {
        "Title": (
            f"{server.get('ServerName', 'Emby')} 上新建 "
            f"{item.get('SeriesName')} - "
            f"S{item.get('ParentIndexNumber')}, Ep{item.get('IndexNumber')} - "
            f"{item.get('Name')}"
        ),
        "Event": "library.new",
        "Item": item,
        "Server": {
            "Name": server.get("ServerName", "Emby"),
            "Version": server.get("Version", "4.9.3.0"),
            "Url": load_env(ENV_FILE).get(
                "EMBY_PUBLIC_URL", "https://dm.aabbss.de"
            ),
        },
    }
    request = urllib.request.Request(
        args.notifier_url,
        data=json.dumps(event, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        if response.status != 200:
            raise RuntimeError(
                f"Replay failed for item {item.get('Id')}: HTTP {response.status}"
            )
    print(f"Queued item {item.get('Id')}")

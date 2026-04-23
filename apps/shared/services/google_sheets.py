from __future__ import annotations

import re


def extract_sheet_id(url: str) -> str | None:
    if not url:
        return None

    patterns = [
        r"/spreadsheets/d/([a-zA-Z0-9-_]+)",
        r"id=([a-zA-Z0-9-_]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def build_export_url(sheet_id: str, file_format: str = "xlsx", gid: str | None = None) -> str:
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format={file_format}"
    if gid:
        url += f"&gid={gid}"
    return url

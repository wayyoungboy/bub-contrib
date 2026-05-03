#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "requests>=2.31.0",
# ]
# ///

"""
DingTalk message sender script.
Send text/markdown messages to DingTalk groups or users via Robot API.
"""

import argparse
import json
import os
import re
import sys
from typing import Any

import requests

OPENAPI_BASE = "https://api.dingtalk.com"
TOKEN_URL = f"{OPENAPI_BASE}/v1.0/oauth2/accessToken"

# Detect markdown features: headings, bold/italic, lists, links, code, or multi-line
_MARKDOWN_RE = re.compile(r"^[#*>-]|[*_`#\[\]]|\n", re.MULTILINE)


def _detect_msg_key(content: str, *, msg_key: str | None) -> str:
    """Choose msg_key: 'sampleText' for plain text, 'sampleMarkdown' for markdown."""
    if msg_key and msg_key != "auto":
        return msg_key
    return "sampleMarkdown" if _MARKDOWN_RE.search(content) else "sampleText"


def get_access_token(client_id: str, client_secret: str) -> str:
    """Get DingTalk access token."""
    resp = requests.post(
        TOKEN_URL,
        json={"appKey": client_id, "appSecret": client_secret},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    token = data.get("accessToken")
    if not token:
        raise RuntimeError(f"Failed to get token: {data.get('message', 'unknown')}")
    return str(token)


def send_message(
    client_id: str,
    client_secret: str,
    chat_id: str,
    content: str,
    *,
    title: str = "Bub Reply",
    msg_key: str = "auto",
) -> dict[str, Any]:
    """Send a text or markdown message to DingTalk, auto-detecting format."""
    token = get_access_token(client_id, client_secret)
    headers = {
        "Content-Type": "application/json",
        "x-acs-dingtalk-access-token": token,
    }

    resolved_key = _detect_msg_key(content, msg_key=msg_key)
    if resolved_key == "sampleMarkdown":
        msg_param = {"text": content, "title": title}
    else:
        msg_param = {"content": content}

    if chat_id.startswith("group:"):
        url = f"{OPENAPI_BASE}/v1.0/robot/groupMessages/send"
        payload = {
            "robotCode": client_id,
            "openConversationId": chat_id[6:],
            "msgKey": resolved_key,
            "msgParam": json.dumps(msg_param, ensure_ascii=False),
        }
    else:
        url = f"{OPENAPI_BASE}/v1.0/robot/oToMessages/batchSend"
        payload = {
            "robotCode": client_id,
            "userIds": [chat_id],
            "msgKey": resolved_key,
            "msgParam": json.dumps(msg_param, ensure_ascii=False),
        }

    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    result = resp.json() if resp.text else {}
    errcode = result.get("errcode")
    if errcode not in (None, 0):
        raise RuntimeError(
            f"DingTalk send failed: errcode={errcode} msg={result.get('message', '')}"
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Send message to DingTalk")
    parser.add_argument(
        "--chat-id", "-c", required=True, help="Target chat ID (group:xxx or user_id)"
    )
    parser.add_argument(
        "--content", "-m", required=True, help="Message content (markdown)"
    )
    parser.add_argument("--title", "-t", default="Bub Reply", help="Message title")
    parser.add_argument(
        "--client-id",
        default=os.environ.get("BUB_DINGTALK_CLIENT_ID"),
        help="DingTalk app client_id",
    )
    parser.add_argument(
        "--client-secret",
        default=os.environ.get("BUB_DINGTALK_CLIENT_SECRET"),
        help="DingTalk app client_secret",
    )
    args = parser.parse_args()

    if not args.client_id or not args.client_secret:
        print(
            "Error: BUB_DINGTALK_CLIENT_ID and BUB_DINGTALK_CLIENT_SECRET are required"
        )
        sys.exit(1)

    try:
        send_message(
            args.client_id,
            args.client_secret,
            args.chat_id,
            args.content,
            title=args.title,
        )
        print(f"Message sent to {args.chat_id}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

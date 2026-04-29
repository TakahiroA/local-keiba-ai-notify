import os
import requests


LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


class LineSendError(RuntimeError):
    pass


def send_line_message(text: str, *, token: str | None = None, user_id: str | None = None) -> None:
    """LINE Messaging APIでPush通知する。"""
    token = token or os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = user_id or os.getenv("LINE_USER_ID")

    if not token:
        raise LineSendError("LINE_CHANNEL_ACCESS_TOKEN が未設定です")
    if not user_id:
        raise LineSendError("LINE_USER_ID が未設定です")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": text[:4900]}],
    }

    res = requests.post(LINE_PUSH_URL, headers=headers, json=payload, timeout=15)
    if res.status_code not in (200, 202):
        raise LineSendError(f"LINE送信失敗: {res.status_code} {res.text}")

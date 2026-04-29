import os
import requests

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")

if not LINE_CHANNEL_ACCESS_TOKEN:
    raise RuntimeError("LINE_CHANNEL_ACCESS_TOKEN が設定されていません")

if not LINE_USER_ID:
    raise RuntimeError("LINE_USER_ID が設定されていません")

url = "https://api.line.me/v2/bot/message/push"

headers = {
    "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}

payload = {
    "to": LINE_USER_ID,
    "messages": [
        {
            "type": "text",
            "text": "LINE通知テスト成功です。"
        }
    ]
}

res = requests.post(url, headers=headers, json=payload, timeout=15)
print(res.status_code)
print(res.text)

if res.status_code == 200:
    print("送信成功")
else:
    print("送信失敗")
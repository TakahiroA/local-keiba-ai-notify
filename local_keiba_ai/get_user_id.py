from flask import Flask, request
import json

app = Flask(__name__)

@app.route("/callback", methods=["POST"])
def callback():
    body = request.get_json()

    print("LINEから受信しました:")
    print(json.dumps(body, ensure_ascii=False, indent=2))

    events = body.get("events", [])
    for event in events:
        source = event.get("source", {})
        user_id = source.get("userId")

        if user_id:
            print("\n==============================")
            print("あなたの LINE_USER_ID はこれです:")
            print(user_id)
            print("==============================\n")

    return "OK"

if __name__ == "__main__":
    app.run(port=5000)
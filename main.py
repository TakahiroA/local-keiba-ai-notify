from datetime import datetime

from flask import Flask, render_template_string, request

from features import enrich_horses
from model import build_score, make_prediction
from scraper import find_race_id, get_horses, get_race_info, normalize_race_id

app = Flask(__name__)

# netkeiba地方競馬(NAR)の race_id に使われる場コード。
# race_id は原則: YYYY + 場コード2桁 + MMDD + RR
# 例: 2026年4月29日 園田9R => 202650042909
PLACES = {
    "30": "門別",
    "35": "盛岡",
    "36": "水沢",
    "42": "浦和",
    "43": "船橋",
    "44": "大井",
    "45": "川崎",
    "46": "金沢",
    "47": "笠松",
    "48": "名古屋",
    "50": "園田",
    "51": "姫路",
    "54": "高知",
    "55": "佐賀",
    "65": "帯広ば",
}

HTML = """
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>🏇地方競馬AI ゆまちゃん🏇</title>
<style>
:root{--bg:#eef2f7;--card:#fff;--text:#111827;--muted:#6b7280;--line:#e5e7eb;--blue:#2563eb;--blue2:#1d4ed8;--soft:#eff6ff;}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html{font-size:16px}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans","Yu Gothic",sans-serif;background:linear-gradient(180deg,#dbeafe 0%,var(--bg) 190px);color:var(--text);padding:10px 10px 92px;}
.container{width:100%;max-width:500px;margin:0 auto;}
.header{padding:12px 2px 10px;}
.header h1{margin:0;font-size:24px;line-height:1.15;letter-spacing:-.04em;}
.header p{margin:7px 0 0;color:var(--muted);font-size:13px;line-height:1.45;}
.card{background:rgba(255,255,255,.97);border:1px solid rgba(255,255,255,.9);border-radius:18px;box-shadow:0 10px 24px rgba(15,23,42,.09);padding:13px;overflow:hidden;}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:9px;}
.field{margin-top:10px;min-width:0;}
.field:first-child{margin-top:0;}
.field label{display:block;font-size:12px;font-weight:800;color:#374151;margin:0 0 5px 2px;}
input,select,button{display:block;width:100%;max-width:100%;height:44px;min-height:44px;padding:9px 11px;border-radius:12px;border:1px solid var(--line);background:#fff;color:var(--text);font-size:16px;line-height:1.2;outline:none;appearance:auto;-webkit-appearance:none;}
input[type="date"]{appearance:none;-webkit-appearance:none;text-align:left;min-width:0;}
select{background-image:linear-gradient(45deg,transparent 50%,#111827 50%),linear-gradient(135deg,#111827 50%,transparent 50%);background-position:calc(100% - 18px) 18px,calc(100% - 12px) 18px;background-size:6px 6px,6px 6px;background-repeat:no-repeat;padding-right:34px;}
input:focus,select:focus{border-color:var(--blue);box-shadow:0 0 0 3px rgba(37,99,235,.12);}
button{margin-top:13px;background:linear-gradient(135deg,var(--blue),var(--blue2));color:#fff;border:none;font-weight:900;letter-spacing:.02em;box-shadow:0 8px 16px rgba(37,99,235,.24);}
button:disabled{opacity:.72;}
.actions{display:flex;gap:8px;align-items:center;margin-top:10px;}
.reset{display:inline-flex;align-items:center;justify-content:center;min-height:34px;padding:7px 11px;border-radius:999px;background:var(--soft);color:var(--blue2);font-size:13px;font-weight:800;text-decoration:none;}
.hint{margin-top:10px;padding:9px 10px;border-radius:12px;background:#f9fafb;color:var(--muted);font-size:12px;line-height:1.5;}
.result-card{margin-top:13px;padding:0;overflow:hidden;}
.result-head{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:11px 13px;background:#111827;color:white;}
.result-head strong{font-size:14px;}
.badge{display:inline-flex;align-items:center;border-radius:999px;padding:4px 8px;background:rgba(255,255,255,.14);font-size:11px;color:#e5e7eb;white-space:nowrap;}
.result{padding:13px;font-size:14px;line-height:1.55;background:#fff;}
.loading{display:none;margin-top:10px;padding:10px;border-radius:12px;background:#fff7ed;color:#9a3412;font-size:13px;line-height:1.45;}
.result h2,.result h3{margin:0 0 8px}.judge-card{border-radius:16px;padding:14px;margin-bottom:12px;border:1px solid #e5e7eb;background:#f9fafb}.judge-card.win{background:#ecfdf5;border-color:#bbf7d0}.judge-card.light{background:#fffbeb;border-color:#fde68a}.judge-card.skip{background:#f8fafc;border-color:#cbd5e1}.judge-card.error{background:#fef2f2;border-color:#fecaca}.judge-title{font-size:20px;font-weight:900;margin-bottom:6px}.judge-reason{font-size:14px;color:#374151}.metric-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:10px 0 12px}.metric{border:1px solid #e5e7eb;border-radius:13px;padding:9px;background:#fff}.metric.wide{grid-column:1/-1}.metric-label{font-size:11px;color:#6b7280;font-weight:800}.metric-value{font-size:15px;font-weight:900;margin-top:2px}.metric-sub{display:inline-block;margin-top:2px;font-size:12px;color:#4b5563;font-weight:800}.badge2{display:inline-flex;border-radius:999px;padding:2px 7px;font-size:11px;font-weight:900;margin-left:4px;vertical-align:1px}.good{background:#dcfce7;color:#166534}.mid{background:#e0f2fe;color:#075985}.bad{background:#fee2e2;color:#991b1b}.warn{background:#fef3c7;color:#92400e}.section{margin-top:14px}.section-title{font-weight:900;font-size:16px;margin-bottom:8px}.rank-card{border:1px solid #e5e7eb;border-radius:14px;padding:11px;margin-bottom:8px;background:#fff}.rank-main{display:flex;align-items:flex-start;gap:8px;justify-content:space-between}.rank-name{font-weight:900;font-size:15px}.rank-sub{color:#4b5563;font-size:13px;margin-top:5px}.grade-row{display:flex;flex-wrap:wrap;gap:5px;margin-top:8px}.grade-chip{border-radius:999px;padding:3px 8px;font-size:12px;font-weight:800;background:#f3f4f6;color:#374151}.grade-chip.a{background:#dcfce7;color:#166534}.grade-chip.b{background:#e0f2fe;color:#075985}.grade-chip.c{background:#fee2e2;color:#991b1b}details{border:1px solid #e5e7eb;border-radius:14px;background:#fff;margin:10px 0;overflow:hidden}summary{cursor:pointer;padding:11px 12px;font-weight:900;background:#f9fafb}details .detail-body{padding:11px 12px;border-top:1px solid #e5e7eb;color:#374151}.reason-list{margin:0;padding-left:18px}.reason-list li{margin:5px 0}.ref-card{border:2px solid #2563eb;background:#eff6ff;border-radius:16px;padding:13px;margin-top:12px}.ref-title{font-size:17px;font-weight:900;color:#1d4ed8}.bet-line{border-radius:12px;background:#fff;padding:10px;margin-top:8px;border:1px solid #bfdbfe}.bet-main{font-weight:900}.bet-sub{font-size:12px;color:#4b5563;margin-top:3px}.criteria-grid{display:grid;grid-template-columns:1fr;gap:7px}.criteria-item{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:9px;font-size:13px}.small-note{color:#6b7280;font-size:12px;line-height:1.5}.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
@media(max-width:430px){
  body{padding:8px 8px 90px;background:linear-gradient(180deg,#dbeafe 0%,var(--bg) 160px);}
  .header{padding:10px 2px 8px;}
  .header h1{font-size:22px;}
  .header p{font-size:12.5px;}
  .card{border-radius:16px;padding:12px;}
  .grid{grid-template-columns:1fr;gap:0;}
  .field{margin-top:9px;}
  input,select,button{height:42px;min-height:42px;border-radius:11px;padding:8px 10px;font-size:16px;}
  button{margin-top:12px;}
  .hint{font-size:11.5px;}
  .result{font-size:13px;padding:12px;line-height:1.55;}
}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>🏇地方競馬AI ゆまちゃん🏇</h1>
    <p>地方netkeibaの出馬表・オッズ・過去走から、安全側に判定します。</p>
  </div>
  <div class="card">
    <form action="/run" method="post" autocomplete="off" id="predict-form">
      <div class="field"><label>race_idを直接入力する場合</label><input type="text" name="race_id" placeholder="例: 202650042909"></div>
      <div class="hint">race_idを入れた場合は、下の日付・競馬場・レース番号より優先します。</div>
      <div class="field"><label>日付</label><input type="date" name="date" value="{{today}}"></div>
      <div class="grid">
        <div class="field"><label>競馬場</label><select name="place"><option value="" {% if not selected_place %}selected{% endif %}>選択してください</option>{% for code,name in places.items() %}<option value="{{code}}" {% if code == selected_place %}selected{% endif %}>{{name}}</option>{% endfor %}</select></div>
        <div class="field"><label>レース</label><select name="race_no"><option value="" {% if not selected_race_no %}selected{% endif %}>選択してください</option>{% for i in range(1,13) %}<option value="{{i}}" {% if selected_race_no and i == selected_race_no|int %}selected{% endif %}>{{i}}R</option>{% endfor %}</select></div>
      </div>
      <div class="field"><label>予算</label><input type="number" name="budget" value="{{budget}}" min="100" step="100" required></div>
      <button type="submit" id="submit-button">予想する</button>
      <div class="loading" id="loading-box">予想中です。地方競馬はページ取得が重いことがあるため、取得できない場合はrace_id直接入力も試してください。</div>
    </form>
    <div class="actions"><a class="reset" href="/">入力をリセット</a></div>
    <div class="hint">地方版は中央版よりスクレイピング失敗が起きやすいです。まずは大井・園田・高知など、検索結果に出るrace_idで動作確認してください。</div>
  </div>
  {% if result %}
  <div class="card result-card">
    <div class="result-head"><strong>予想結果</strong><span class="badge">地方版</span></div>
    <div class="result">{{result|safe}}</div>
  </div>
  {% endif %}
</div>
<script>
const form=document.getElementById('predict-form');const button=document.getElementById('submit-button');const loading=document.getElementById('loading-box');if(form){form.addEventListener('submit',()=>{button.disabled=true;button.textContent='予想中...';loading.style.display='block';});}
</script>
</body>
</html>
"""


@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def render(result=None, today=None, place="", race_no="", budget=3000):
    return render_template_string(
        HTML,
        places=PLACES,
        result=result,
        today=today or datetime.today().strftime("%Y-%m-%d"),
        selected_place=place or "",
        selected_race_no=race_no or "",
        budget=budget or 3000,
    )


@app.route("/")
def index():
    return render()


@app.route("/run", methods=["GET"])
def run_get_block():
    return render("フォームから実行してください。race_id直接入力も使えます。")


@app.route("/run", methods=["POST"])
def run():
    try:
        print("地方予想開始")
        race_id_raw = request.form.get("race_id", "").strip()
        date_raw = request.form.get("date", "").strip()
        place = request.form.get("place", "").strip()
        race_no_raw = request.form.get("race_no", "").strip()
        budget_raw = request.form.get("budget") or "3000"
        budget = int(budget_raw)

        if race_id_raw:
            race_id = normalize_race_id(race_id_raw)
            date = race_id[:4] + race_id[6:10] if len(race_id) == 12 else ""
        else:
            if not date_raw or not place or not race_no_raw:
                return render("race_idを直接入力するか、日付・競馬場・レース番号を選択してください。", date_raw, place, race_no_raw, budget)
            date = date_raw.replace("-", "")
            race_no = int(race_no_raw)
            race_id = find_race_id(date, place, race_no)

        print("race_id:", race_id)
        if not race_id:
            return render("レースが見つかりませんでした。race_idを直接入力して再実行してください。", date_raw, place, race_no_raw, budget)

        race_info = get_race_info(race_id)
        race_info["target_date"] = date
        print("race_info:", race_info)

        horses = get_horses(race_id)
        print("horses:", len(horses))
        if not horses:
            return render(f"race_id: {race_id}<br>出馬表を取得できませんでした。地方netkeiba側の構造変更、未公開、またはアクセス制限の可能性があります。", date_raw, place, race_no_raw, budget)

        horses = enrich_horses(horses, race_info)
        horses = build_score(horses, race_info)
        result = make_prediction(race_id, race_info, horses, budget)
        print("地方予想完了")
        return render(result, date_raw, place, race_no_raw, budget)
    except Exception as e:
        print("エラー:", e)
        return render(f"エラー: {e}")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)

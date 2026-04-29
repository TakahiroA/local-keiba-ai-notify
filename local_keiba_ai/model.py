import html
import math


def esc(v):
    return html.escape(str(v if v is not None else ""))


def odds_text(odds):
    return "未取得" if odds is None else str(round(odds, 1))


def cls_to_jp(cls):
    return {"good":"良","mid":"中","bad":"低","warn":"注"}.get(cls,"中")


def confidence_label(v):
    if v >= 0.65: return f"{round(v,3)}（高）"
    if v >= 0.50: return f"{round(v,3)}（中）"
    return f"{round(v,3)}（低）"


def confidence_cls(v):
    return "good" if v >= 0.65 else "mid" if v >= 0.50 else "bad"


def pct_label(v, low=0.10, high=0.16):
    p = round(v * 100, 1)
    if v >= high: return f"{p}%（高め）"
    if v >= low: return f"{p}%（標準）"
    return f"{p}%（低め）"


def pct_cls(v, low=0.10, high=0.16):
    return "good" if v >= high else "mid" if v >= low else "warn"


def rate_label(v):
    p = round(v * 100, 1)
    if v >= 0.90: return f"{p}%（良好）"
    if v >= 0.70: return f"{p}%（許容）"
    return f"{p}%（不足）"


def rate_cls(v):
    return "good" if v >= 0.90 else "mid" if v >= 0.70 else "bad"


def data_status_label(data_rate, odds_rate):
    d = round(data_rate * 100, 1)
    o = round(odds_rate * 100, 1)
    if data_rate >= 0.70 and odds_rate >= 0.80:
        status = "OK"
    elif data_rate == 0 or odds_rate == 0:
        status = "取得エラー"
    else:
        status = "注意"
    return f"{status}<br><span class='metric-sub'>過去走 {d}% / オッズ {o}%</span>"


def data_status_cls(data_rate, odds_rate):
    if data_rate >= 0.70 and odds_rate >= 0.80:
        return "good"
    if data_rate == 0 or odds_rate == 0:
        return "bad"
    return "warn"


def gap_label(gap):
    if gap < 0.03: return f"{round(gap,3)}（かなり小さい）"
    if gap < 0.08: return f"{round(gap,3)}（小さめ）"
    if gap < 0.12: return f"{round(gap,3)}（標準）"
    return f"{round(gap,3)}（大きめ）"


def gap_cls(gap):
    return "good" if gap >= 0.10 else "mid" if gap >= 0.03 else "bad"


def ev_label(ev, threshold=None):
    ev = round(ev, 2)
    if threshold is None:
        if ev >= 1.0: return f"{ev}（妙味あり）"
        if ev >= 0.5: return f"{ev}（やや不足）"
        return f"{ev}（低い）"
    return f"{ev}（基準クリア）" if ev >= threshold else f"{ev}（基準未満）"


def grade_value(value, kind):
    if kind in ["stability", "distance"]:
        if value >= 0.55: return "A", "a"
        if value >= 0.40: return "B", "b"
        return "C", "c"
    if kind == "speed":
        if value >= 1.03: return "A", "a"
        if value >= 0.98: return "B", "b"
        return "C", "c"
    if kind == "prob":
        if value >= 0.16: return "A", "a"
        if value >= 0.10: return "B", "b"
        return "C", "c"
    return "B", "b"


def metric(label, value, cls="mid", show_badge=True, extra_class="", raw=False):
    value_html = value if raw else esc(value)
    badge = f" <span class='badge2 {cls}'>{esc(cls_to_jp(cls))}</span>" if show_badge else ""
    return f"<div class='metric {extra_class}'><div class='metric-label'>{esc(label)}</div><div class='metric-value'>{value_html}{badge}</div></div>"


def judge_card(title, reason, mode="skip"):
    return f"<div class='judge-card {mode}'><div class='judge-title'>{esc(title)}</div><div class='judge-reason'>{esc(reason)}</div></div>"


def render_summary(race_id, race_info, axis, gap, data_rate, odds_rate, confidence):
    parts = [f"<div class='small-note mono'>race_id: {esc(race_id)}</div>"]
    if race_info.get("name") or race_info.get("info"):
        parts.append(f"<div class='small-note'>{esc(race_info.get('name',''))}<br>{esc(race_info.get('info',''))}</div>")
    parts.append("<div class='section'><div class='section-title'>判定サマリー</div><div class='metric-grid'>")
    parts.append(metric("軸候補", f"{axis.get('num','')} {axis.get('name','')}", "mid"))
    parts.append(metric("信頼度", confidence_label(confidence), confidence_cls(confidence)))
    parts.append(metric("想定勝率", pct_label(axis.get("prob",0)), pct_cls(axis.get("prob",0))))
    parts.append(metric("1位と2位の差", gap_label(gap), gap_cls(gap)))
    parts.append(metric("データ状態", data_status_label(data_rate, odds_rate), data_status_cls(data_rate, odds_rate), show_badge=False, extra_class="wide", raw=True))
    parts.append("</div></div>")
    return "".join(parts)


def render_criteria():
    return """
<details>
  <summary>評価基準・買い条件の目安を見る</summary>
  <div class="detail-body">
    <div class="criteria-grid">
      <div class="criteria-item"><b>A/B/C評価</b><br>安定・距離：A=0.55以上 / B=0.40以上 / C=0.40未満<br>上がり：A=1.03以上 / B=0.98以上 / C=0.98未満<br>※過去走データ取得率とオッズ取得率は能力評価ではなく、取得状態として表示します。</div>
      <div class="criteria-item"><b>信頼度</b><br>高=0.65以上 / 中=0.50以上 / 低=0.50未満</div>
      <div class="criteria-item"><b>買い条件</b><br>基本：過去走70%以上、オッズ80%以上、情報取得エラーなし<br>ワイド：EV0.35以上 + 信頼度0.55以上 + 差0.05以上<br>馬連：EV0.30以上 + 信頼度0.55以上 + 差0.05以上<br>3連複：EV0.22以上 + 信頼度0.55以上 + 差0.05以上<br>単勝：EV1.30以上 + 勝率14%以上 + 信頼度0.60以上 + 差0.08以上</div>
      <div class="criteria-item"><b>注意</b><br>ワイド・馬連・3連複のEVは単勝オッズからの近似です。実オッズとはズレるので、最終確認は必要です。</div>
    </div>
  </div>
</details>
"""


def render_top_horses(horses):
    parts = ["<div class='section'><div class='section-title'>上位評価</div>"]
    for i, h in enumerate(horses[:5], 1):
        sg, sc = grade_value(h.get("stability",0), "stability")
        vg, vc = grade_value(h.get("speed",0), "speed")
        dg, dc = grade_value(h.get("distance_score",0), "distance")
        parts.append(
            f"<div class='rank-card'>"
            f"<div class='rank-main'><div><div class='rank-name'>{i}位　{esc(h.get('num',''))} {esc(h.get('name',''))}</div>"
            f"<div class='rank-sub'>勝率 {round(h.get('prob',0)*100,1)}% / 単勝 {esc(odds_text(h.get('odds')))} / 評価 {round(h.get('score',0),3)}</div></div></div>"
            f"<div class='grade-row'><span class='grade-chip {sc}'>安定 {sg}</span><span class='grade-chip {vc}'>上がり {vg}</span><span class='grade-chip {dc}'>距離 {dg}</span></div>"
            f"<details><summary>詳細を見る</summary><div class='detail-body'>"
            f"評価:{round(h.get('score',0),3)} / 勝率:{round(h.get('prob',0)*100,1)}% / 単勝:{esc(odds_text(h.get('odds')))}<br>"
            f"安定:{round(h.get('stability',0),3)} / 上がり:{round(h.get('speed',0),3)} / 距離:{round(h.get('distance_score',0),3)} / 過去走:{esc(h.get('runs_count',0))}<br>"
            f"騎手補正:{round(h.get('jockey_score',1),2)} / 馬場補正:{round(h.get('ground_score',1),2)} / コース補正:{round(h.get('course_score',1),2)} / 展開補正:{round(h.get('pace_bonus',1),2)}"
            f"</div></details></div>"
        )
    parts.append("</div>")
    return "".join(parts)


def pace_type(horses):
    front_count = len([h for h in horses if h.get("style", 8) <= 4])
    if front_count >= 5: return "ハイペース想定"
    if front_count <= 2: return "スロー想定"
    return "平均ペース想定"


def build_score(horses, race_info):
    pace = pace_type(horses)
    for h in horses:
        odds = h.get("odds")
        market = 0 if odds is None else min(0.20, 1 / max(odds, 1.0))
        pace_bonus = 1.0
        if pace == "ハイペース想定" and h.get("style", 8) >= 7: pace_bonus = 1.12
        if pace == "スロー想定" and h.get("style", 8) <= 4: pace_bonus = 1.12
        style_score = 1 / (h.get("style", 8) + 1)
        h["score"] = (h.get("stability",0.50)*0.33 + h.get("speed",0.50)*0.20 + h.get("distance_score",0.50)*0.23 + market*0.08 + style_score*0.16) * h.get("jockey_score",1.0) * h.get("ground_score",1.0) * h.get("course_score",1.0) * pace_bonus
        h["pace_bonus"] = pace_bonus
        h["pace_type"] = pace
        h["market_score"] = market
    total = sum(h.get("score",0) for h in horses)
    for h in horses:
        h["prob"] = h["score"] / total if total > 0 else 0
        h["value"] = h["prob"] * h["odds"] if h.get("odds") is not None else None
    horses.sort(key=lambda x: x.get("score",0), reverse=True)
    return horses


def rates(horses):
    n = max(len(horses), 1)
    return sum(1 for h in horses if h.get("data_ok")) / n, sum(1 for h in horses if h.get("odds") is not None) / n


def odds_sanity_check(horses):
    vals = [h["odds"] for h in horses if h.get("odds") is not None]
    if not vals: return False, "オッズが1件も取得できていません"
    if len(vals) < max(5, int(len(horses) * 0.70)): return False, "オッズ取得数が少なすぎます"
    if min(vals) < 1.0: return False, "単勝オッズとして不自然な1.0未満の値があります"
    if min(vals) > 20: return False, "全馬の単勝オッズが20倍超です。単勝列ではない数値を拾っている可能性があります"
    if max(vals) > 999.9: return False, "1000倍超のオッズが混ざっています。列ズレまたはパース異常の可能性があります"
    return True, "OK"


def geom_odds(*odds):
    vals = [o for o in odds if o is not None and o > 0]
    return None if not vals else math.prod(vals) ** (1 / len(vals))


def add_candidate(candidates, bet_type, target, names, prob, est_odds, threshold, weight, note=""):
    if est_odds is None: return
    candidates.append({"type":bet_type,"target":target,"names":names,"prob":prob,"est_odds":est_odds,"ev":prob*est_odds,"threshold":threshold,"weight":weight,"note":note})


def build_candidate_bets(axis, partners):
    candidates = []
    if axis.get("odds") is None: return candidates
    usable = [p for p in partners if p.get("odds") is not None]
    if not usable: return candidates
    add_candidate(candidates, "単勝", f"{axis['num']}", f"{axis['name']}", axis.get("prob",0), axis.get("odds"), 1.30, 0.8)
    for p in usable[:4]:
        pair_prob = axis.get("prob",0) * p.get("prob",0)
        base = geom_odds(axis.get("odds"), p.get("odds"))
        add_candidate(candidates, "ワイド", f"{axis['num']}-{p['num']}", f"{axis['name']} - {p['name']}", pair_prob*2.3, base, 0.35, 3.0)
        add_candidate(candidates, "馬連", f"{axis['num']}-{p['num']}", f"{axis['name']} - {p['name']}", pair_prob*1.8, base*1.5 if base else None, 0.30, 1.8)
    score_partners = sorted(usable[:5], key=lambda h: h.get("score",0), reverse=True)[:2]
    popular_partners = sorted(usable[:6], key=lambda h: h.get("odds",999.9))[:2]
    keys, probs, odds = set(), [], []
    for p1 in score_partners:
        for p2 in popular_partners:
            if p1.get("num") == p2.get("num"): continue
            key = tuple(sorted([str(axis.get("num")), str(p1.get("num")), str(p2.get("num"))]))
            if key in keys: continue
            keys.add(key)
            probs.append(axis.get("prob",0)*p1.get("prob",0)*p2.get("prob",0)*6.0)
            base = geom_odds(axis.get("odds"), p1.get("odds"), p2.get("odds"))
            if base: odds.append(base * 1.8)
    if probs and odds:
        nums1 = ",".join(str(h.get("num")) for h in score_partners)
        nums2 = ",".join(str(h.get("num")) for h in popular_partners)
        names1 = ",".join(str(h.get("name")) for h in score_partners)
        names2 = ",".join(str(h.get("name")) for h in popular_partners)
        add_candidate(candidates, "3連複フォーメーション", f"軸:{axis['num']} / 相手:{nums1} / 押さえ:{nums2}", f"軸:{axis['name']} / 相手:{names1} / 押さえ:{names2}", sum(probs)/len(probs), sum(odds)/len(odds), 0.22, 1.4)
    return candidates


def single_win_is_strict(axis, gap, confidence, ev):
    return ev >= 1.30 and axis.get("prob",0) >= 0.14 and confidence >= 0.60 and gap >= 0.08


def single_win_is_light(axis, gap, confidence, ev):
    return ev >= 1.80 and axis.get("prob",0) >= 0.09 and confidence >= 0.50 and gap >= 0.06 and axis.get("odds",0) >= 8.0


def classify_bets(candidates, axis, gap, confidence):
    official, light = [], []
    for b in candidates:
        if b["ev"] < b["threshold"]: continue
        if b["type"] == "単勝":
            if single_win_is_strict(axis, gap, confidence, b["ev"]): official.append(b)
            elif single_win_is_light(axis, gap, confidence, b["ev"]): light.append(b)
            continue
        if confidence >= 0.55 and gap >= 0.05: official.append(b)
        elif confidence >= 0.48 and gap >= 0.035 and b["ev"] >= b["threshold"] * 0.85: light.append(b)
    def top(items, limits):
        out=[]
        for t, n in limits.items(): out += sorted([b for b in items if b["type"]==t], key=lambda x:x["ev"], reverse=True)[:n]
        order={"ワイド":0,"馬連":1,"3連複フォーメーション":2,"単勝":3}
        return sorted(out, key=lambda x:(order.get(x["type"],9), -x["ev"]))
    return top(official,{"ワイド":2,"馬連":2,"3連複フォーメーション":2,"単勝":1}), top(light,{"ワイド":2,"馬連":1,"3連複フォーメーション":1,"単勝":1})


def best_by_type(candidates):
    out=[]
    for t in ["単勝","ワイド","馬連","3連複フォーメーション"]:
        xs=[b for b in candidates if b["type"]==t]
        if xs: out.append(max(xs, key=lambda b:b["ev"]))
    return out


def render_miokuri_detail(axis, gap, candidates, confidence):
    reasons=[f"1位と2位の差: {gap_label(gap)}", f"軸候補の想定勝率: {pct_label(axis.get('prob',0))}", f"信頼度: {confidence_label(confidence)}"]
    for b in best_by_type(candidates):
        if b["type"] == "単勝":
            reasons.append(f"単勝EV: {ev_label(b['ev'], 1.30)}")
            if b["ev"] >= 1.15 and not single_win_is_strict(axis, gap, confidence, b["ev"]): reasons.append("単勝EVは高めですが、勝率・信頼度・相手との差が足りません")
            break
    return "<details open><summary>見送り理由</summary><div class='detail-body'><ul class='reason-list'>" + "".join(f"<li>{esc(r)}</li>" for r in reasons) + "</ul></div></details>"


def render_reference_bets(candidates, budget):
    if not candidates: return ""
    priority={"ワイド":0,"馬連":1,"3連複フォーメーション":2,"単勝":3}
    usable=[b for b in candidates if b["type"] in priority]
    if not usable: return ""
    selected=[]
    wide=sorted([b for b in usable if b["type"]=="ワイド"], key=lambda b:b["ev"], reverse=True)
    if wide: selected.append(wide[0])
    for b in sorted([b for b in usable if b["type"]!="ワイド"], key=lambda b:(priority.get(b["type"],9), -b["ev"])):
        if len(selected)>=2: break
        selected.append(b)
    ref_budget=(min(1000, max(100, int(budget*0.30)))//100)*100
    if not selected or ref_budget<=0: return ""
    amounts=[ref_budget] if len(selected)==1 else ([max(100,(int(ref_budget*0.70)//100)*100),0])
    if len(selected)>1: amounts[1]=max(100, ref_budget-amounts[0])
    parts=["<div class='ref-card'><div class='ref-title'>もし買うなら（参考・少額）</div><div class='small-note'>正式推奨ではありません。買い条件未満なので、金額は抑える前提です。</div>"]
    if max(b["ev"] for b in selected) < 0.20: parts.append("<div class='small-note'>参考EVも低いため、買わない判断が本線です。</div>")
    for b, amount in zip(selected, amounts):
        parts.append(f"<div class='bet-line'><div class='bet-main'>{esc(b['type'])} {esc(b['target'])}　{amount}円</div><div class='bet-sub'>{esc(b['names'])}<br>EV目安: {esc(ev_label(b['ev'], b.get('threshold')))}</div></div>")
    return "".join(parts) + "</div>"


def allocate_bets(bets, budget, mode="official"):
    budget=(int(budget)//100)*100
    if not bets or budget<=0: return []
    allocations=[]; remaining=budget
    singles=sorted([b for b in bets if b["type"]=="単勝"], key=lambda b:b["ev"], reverse=True)
    if singles:
        amount=min((int(budget*0.40)//100)*100, remaining)
        if amount>0: allocations.append((singles[0], amount)); remaining-=amount
    rest=[b for b in bets if b["type"]!="単勝"]
    if rest and remaining>0:
        total_w=sum(b["weight"] for b in rest); used=0
        for i,b in enumerate(rest):
            amount=remaining-used if i==len(rest)-1 else (int(remaining*(b["weight"]/total_w))//100)*100
            if i < len(rest)-1: used += amount
            if amount>0: allocations.append((b, amount))
    order={"ワイド":0,"馬連":1,"3連複フォーメーション":2,"単勝":3}
    return sorted(allocations, key=lambda x:order.get(x[0]["type"],9))


def render_bets(allocations, budget):
    parts=["<div class='section'><div class='section-title'>推奨馬券</div>"]
    for b, amount in allocations:
        parts.append(f"<div class='bet-line'><div class='bet-main'>{esc(b['type'])} {esc(b['target'])}　{amount}円</div><div class='bet-sub'>{esc(b['names'])}<br>EV目安: {esc(ev_label(b['ev'], b.get('threshold')))}</div></div>")
    used=sum(a for _,a in allocations)
    if used<budget: parts.append(f"<div class='small-note'>リスク調整のため、未使用予算：{budget-used}円</div>")
    return "".join(parts)+"</div>"


def provisional_result(race_id, race_info, horses, reason, gap, data_rate, odds_rate, confidence):
    axis=horses[0]
    return render_summary(race_id,race_info,axis,gap,data_rate,odds_rate,confidence)+judge_card("暫定評価", f"{reason}。買い目と金額は出しません。", "light")+render_criteria()+render_top_horses(horses)


def make_prediction(race_id, race_info, horses, budget):
    if len(horses)<5: return judge_card("見送り", "頭数不足です", "skip")
    axis, second = horses[0], horses[1]
    gap = axis.get("score",0) - second.get("score",0)
    data_rate, odds_rate = rates(horses)
    axis_prob, second_prob = axis.get("prob",0), second.get("prob",0)
    prob_gap=max(0, axis_prob-second_prob)
    relative_score_gap=gap/max(axis.get("score",0), 1e-9)
    confidence=min(0.95, axis_prob*2.5 + prob_gap*3.0 + relative_score_gap*0.15 + axis.get("stability",0.5)*0.10 + data_rate*0.10 + odds_rate*0.10)
    base=render_summary(race_id, race_info, axis, gap, data_rate, odds_rate, confidence)
    if data_rate==0: return base+judge_card("情報取得エラー", "情報を取得できませんでした（過去走データが0件です）", "error")+render_criteria()+render_top_horses(horses)
    if data_rate<0.30: return base+judge_card("情報取得エラー", "情報を取得できませんでした（過去走データ取得率が低すぎます）", "error")+render_criteria()+render_top_horses(horses)
    if data_rate<0.70: return provisional_result(race_id,race_info,horses,"過去走データが不足しているため",gap,data_rate,odds_rate,confidence)
    ok, reason=odds_sanity_check(horses)
    if odds_rate==0: return provisional_result(race_id,race_info,horses,"オッズを1頭も取得できていないため",gap,data_rate,odds_rate,confidence)
    if not ok: return provisional_result(race_id,race_info,horses,reason,gap,data_rate,odds_rate,confidence)
    if odds_rate<0.80: return provisional_result(race_id,race_info,horses,"オッズ取得率が80%未満のため",gap,data_rate,odds_rate,confidence)
    if confidence<0.35: return base+judge_card("見送り", "軸の信頼度が低いため", "skip")+render_criteria()+render_top_horses(horses)
    partners=[h for h in horses[1:7] if h.get("odds") is not None][:5]
    if len(partners)<2 or axis.get("odds") is None: return provisional_result(race_id,race_info,horses,"軸または相手のオッズが不足しているため",gap,data_rate,odds_rate,confidence)
    candidates=build_candidate_bets(axis, partners)
    official_bets, light_bets=classify_bets(candidates, axis, gap, confidence)
    selected=official_bets if official_bets else light_bets
    mode="official" if official_bets else "light"
    if not selected:
        return base+judge_card("見送り", "買い条件を満たす馬券がありません", "skip")+render_miokuri_detail(axis,gap,candidates,confidence)+render_reference_bets(candidates,budget)+render_criteria()+render_top_horses(horses)
    title="勝負レース" if mode=="official" else "軽め勝負"
    reason="買い条件を満たす馬券があります" if mode=="official" else "妙味はありますが、軸信頼度は中程度です。金額は偏りすぎないよう調整します"
    allocations=allocate_bets(selected, budget, mode)
    return base+judge_card(title, reason, "win" if mode=="official" else "light")+render_bets(allocations,budget)+render_criteria()+render_top_horses(horses)

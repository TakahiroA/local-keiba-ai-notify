from scraper import get_past_runs


LOCAL_TOP_JOCKEYS = [
    # 南関
    "矢野", "御神本", "森泰斗", "笹川", "和田譲", "本田正", "町田", "吉原",
    # 兵庫
    "吉村智", "下原", "田中学", "鴨宮", "廣瀬",
    # 高知・佐賀・東海・北海道など
    "赤岡", "宮川実", "岡部誠", "渡邊竜", "山口勲", "石川倭", "桑村",
]

LOCAL_GOOD_JOCKEYS = [
    "張田昂", "本橋", "野畑", "山崎誠", "今野", "達城", "西啓太",
    "杉浦", "大山龍", "永井", "塚本征", "加藤聡", "飛田愛", "落合玄",
    "阿部龍", "多田誠", "永森", "井上瑛",
]


def jockey_score(name):
    """地方競馬向けの簡易騎手補正。

    注意:
    騎手の勢いは開催・地区で変わるため、ここは固定値にしすぎない。
    精度を上げるなら「競馬場ごとの直近勝率」で置き換える。
    """
    name = name or ""
    for j in LOCAL_TOP_JOCKEYS:
        if j in name:
            return 1.12
    for j in LOCAL_GOOD_JOCKEYS:
        if j in name:
            return 1.06
    return 1.0


def ground_score(ground, style):
    # 地方ダートは重・不良で前が止まりにくいケースがあるため、先行寄りを少し加点。
    if ground in ["重", "不良"]:
        if style <= 5:
            return 1.09
        return 0.97
    if ground == "稍重":
        if style <= 5:
            return 1.04
        return 1.01
    return 1.0


def course_score(place_name, distance, style, num):
    """地方競馬の簡易コース補正。

    これは強い決め打ちではなく、同点付近の序列を動かす程度の補正。
    """
    place_name = place_name or ""
    try:
        num = int(num)
    except Exception:
        num = 0

    bonus = 1.0

    # 浦和・川崎・園田・高知など小回り色が強い場は先行力を少し重視。
    if any(p in place_name for p in ["浦和", "川崎", "園田", "姫路", "高知", "佐賀", "金沢", "笠松"]):
        if style <= 4:
            bonus *= 1.06
        elif style >= 9:
            bonus *= 0.97

    # 大井の外回り・中距離は差しも届きやすい想定に寄せる。
    if "大井" in place_name and distance and distance >= 1600:
        if style >= 6:
            bonus *= 1.04

    # 短距離は基本的に先行寄りを加点。
    if distance and distance <= 1200:
        if style <= 4:
            bonus *= 1.05
        elif style >= 9:
            bonus *= 0.96

    # 内枠が効きやすい小回り短距離だけ軽く加点。
    if distance and distance <= 1400 and num in [1, 2, 3]:
        bonus *= 1.02

    return max(0.92, min(1.12, bonus))


def distance_score(runs, target_distance):
    if not runs or not target_distance:
        return 0.50
    scores = []
    for r in runs:
        if r.get("distance") is None:
            continue
        diff = abs(r["distance"] - target_distance)
        base = 1 / max(r.get("rank") or 18, 1)
        if diff <= 100:
            scores.append(base * 1.05)
        elif diff <= 200:
            scores.append(base)
        elif diff <= 400:
            scores.append(base * 0.80)
        elif diff <= 600:
            scores.append(base * 0.55)
    return sum(scores) / len(scores) if scores else 0.50


def agari_score(agaris):
    if not agaris:
        return 0.50
    avg = sum(agaris) / len(agaris)
    if avg <= 0:
        return 0.50
    # 地方は馬場・距離で上がりの絶対値がブレやすいので中央版よりクリップを控えめにする。
    score = 36.5 / avg
    return max(0.72, min(1.18, score))


def enrich_horses(horses, race_info):
    for h in horses:
        runs = get_past_runs(h.get("url"), target_date=race_info.get("target_date"))
        h["runs_count"] = len(runs)

        if not runs:
            h["stability"] = 0.50
            h["speed"] = 0.50
            h["style"] = 8
            h["distance_score"] = 0.50
            h["data_ok"] = False
        else:
            ranks = [max(r["rank"], 1) for r in runs if r.get("rank") is not None]
            agaris = [r["agari"] for r in runs if r.get("agari") is not None]
            styles = [r["first_pos"] for r in runs if r.get("first_pos") is not None]

            h["stability"] = sum(1 / r for r in ranks) / len(ranks) if ranks else 0.50
            h["speed"] = agari_score(agaris)
            h["style"] = sum(styles) / len(styles) if styles else 8
            h["distance_score"] = distance_score(runs, race_info.get("distance"))
            h["data_ok"] = True

        h["jockey_score"] = jockey_score(h.get("jockey", ""))
        h["ground_score"] = ground_score(race_info.get("ground", "良"), h["style"])
        h["course_score"] = course_score(
            race_info.get("place_name", "") or race_info.get("name", ""),
            race_info.get("distance"),
            h["style"],
            h.get("num"),
        )
    return horses

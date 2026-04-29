"""
中央版にも同じ通知を入れるためのテンプレ。
中央版の scraper / features / model が地方版と同じ関数名なら、notify_local.pyをコピーして、
PLACES と race_id作成部分だけ中央版に合わせれば動きます。

必要な関数インターフェース:
- get_race_info(race_id) -> dict
- get_horses(race_id) -> list[dict]
- enrich_horses(horses, race_info) -> list[dict]
- build_score(horses, race_info) -> list[dict]
- build_candidate_bets(axis, partners)
- classify_bets(candidates, axis, gap, confidence)
- allocate_bets(bets, budget, mode)

中央版のファイルを見せてもらえれば、PLACES/race_id部分まで合わせて作れます。
"""

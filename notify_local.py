import argparse
from datetime import datetime
from zoneinfo import ZoneInfo

from line_client import send_line_message
from notify_db import already_notified, connect, save_notified
from scraper import find_race_id
from shobu_engine import build_line_text, evaluate_race, should_check_now

# main.py の PLACES と同じ地方競馬場コード
PLACES = {
    "30": "門別", "35": "盛岡", "36": "水沢", "42": "浦和", "43": "船橋",
    "44": "大井", "45": "川崎", "46": "金沢", "47": "笠松", "48": "名古屋",
    "50": "園田", "51": "姫路", "54": "高知", "55": "佐賀", "65": "帯広ば",
}


def parse_races(s: str):
    if "-" in s:
        a, b = s.split("-", 1)
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in s.split(",") if x.strip()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y%m%d"))
    parser.add_argument("--places", default="44,50,54", help="例: 44,50,54 / all")
    parser.add_argument("--races", default="1-12", help="例: 1-12 or 9,10,11")
    parser.add_argument("--budget", type=int, default=3000)
    parser.add_argument("--include-light", action="store_true", help="軽め勝負も通知する")
    parser.add_argument("--from-min", type=int, default=15)
    parser.add_argument("--to-min", type=int, default=60)
    parser.add_argument("--dry-run", action="store_true", help="LINE送信せず表示だけ")
    args = parser.parse_args()

    date = args.date.replace("-", "")
    place_codes = list(PLACES.keys()) if args.places == "all" else [p.strip().zfill(2) for p in args.places.split(",") if p.strip()]
    races = parse_races(args.races)
    conn = connect()

    for place in place_codes:
        for race_no in races:
            try:
                race_id = find_race_id(date, place, race_no)
                result = evaluate_race(race_id, date, args.budget)

                if result.mode not in ["official", "light"]:
                    print(f"SKIP {race_id}: {result.title} / {result.reason}")
                    continue
                if result.mode == "light" and not args.include_light:
                    print(f"SKIP LIGHT {race_id}: 軽め勝負は通知対象外")
                    continue
                # 発走時刻が拾える場合だけ、通知時間帯を絞る。拾えない場合は通知対象。
                if not should_check_now(
                    {"name": result.race_name, "info": result.race_info_text},
                    date,
                    from_min=args.from_min,
                    to_min=args.to_min,
                ):
                    print(f"SKIP TIME {race_id}: 通知時間外")
                    continue
                if already_notified(conn, result.notify_key):
                    print(f"SKIP DUP {race_id}: 通知済み")
                    continue

                text = build_line_text(result, label=f"地方 {PLACES.get(place, place)}")
                if args.dry_run:
                    print("----- DRY RUN -----")
                    print(text)
                else:
                    send_line_message(text)
                    save_notified(
                        conn,
                        key=result.notify_key,
                        race_id=race_id,
                        mode=result.mode,
                        title=result.title,
                        axis=f"{result.axis_num} {result.axis_name}",
                    )
                    print(f"SENT {race_id}: {result.title}")
            except Exception as e:
                print(f"ERROR place={place} race={race_no}: {e}")


if __name__ == "__main__":
    main()

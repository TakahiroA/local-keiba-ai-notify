import argparse
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from line_client import send_line_message
from notify_db import already_notified, connect, save_notified
from scraper import find_race_id, get_race_info, get_today_races
from shobu_engine import build_line_text, evaluate_race, should_check_now

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


def parse_races(s: str):
    """'1-12' or '10,11,12' -> list[int]."""
    s = str(s or "").strip()

    if "-" in s:
        a, b = s.split("-", 1)
        return list(range(int(a), int(b) + 1))

    return [int(x) for x in s.split(",") if x.strip()]


def normalize_places(value: str):
    """'all' or '36,44,50' -> list[str] local racecourse codes."""
    value = str(value or "").strip()

    if value.lower() == "all":
        return list(PLACES.keys())

    return [p.strip().zfill(2) for p in value.split(",") if p.strip()]


def has_start_time(race_info: dict) -> bool:
    """Return True only if the race start time appears to be available."""
    if race_info.get("start_time"):
        return True

    text = f"{race_info.get('name', '')} {race_info.get('info', '')}"
    return bool(re.search(r"([0-2]?\d[:：][0-5]\d)", text))


def build_race_info_for_time_check(race_id: str, schedule_item: dict, date: str) -> dict:
    """Combine schedule-list info and detail-page info for time-window checks.

    The heavy AI evaluation should only run when this function can confirm that
    the race is inside the notification window.
    """
    race_info = {
        "name": schedule_item.get("name", ""),
        "info": schedule_item.get("info", ""),
        "place_name": schedule_item.get("place_name", ""),
        "start_time": schedule_item.get("start_time", ""),
        "target_date": date,
    }

    detail = get_race_info(race_id)
    if detail:
        race_info["name"] = detail.get("name") or race_info.get("name", "")
        race_info["info"] = " ".join(
            [
                str(race_info.get("info", "")),
                str(detail.get("info", "")),
            ]
        ).strip()

        for key, value in detail.items():
            if key not in ["name", "info"] and value not in [None, ""]:
                race_info[key] = value

    race_info["target_date"] = date
    return race_info


def iter_target_races(date: str, place_codes, race_nos, use_schedule: bool):
    """Yield candidate race dicts.

    use_schedule=True:
      Use the daily race list and only process real race_id values found there.

    use_schedule=False:
      Fallback to the old place x race_no method.
    """
    if use_schedule:
        races = get_today_races(date, place_codes=place_codes, race_nos=race_nos)
        for race in races:
            yield race
        return

    for place in place_codes:
        for race_no in race_nos:
            race_id = find_race_id(date, place, race_no)
            if not race_id:
                print(f"SKIP {date} {PLACES.get(place, place)}{race_no}R: race_idが見つかりません")
                continue

            yield {
                "race_id": race_id,
                "place": place,
                "place_name": PLACES.get(place, place),
                "race_no": race_no,
                "name": "",
                "info": "",
                "start_time": "",
            }


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--date",
        default=datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y%m%d"),
        help="対象日。例: 20260429 / 2026-04-29",
    )
    parser.add_argument(
        "--places",
        default="all",
        help="地方競馬場コード。例: 44,50,54 / all",
    )
    parser.add_argument(
        "--races",
        default="1-12",
        help="対象レース。例: 1-12 / 9,10,11",
    )
    parser.add_argument(
        "--budget",
        type=int,
        default=3000,
        help="購入予算",
    )
    parser.add_argument(
        "--include-light",
        action="store_true",
        help="軽め勝負も通知する",
    )
    parser.add_argument(
        "--from-min",
        type=int,
        default=20,
        help="発走何分前から通知対象にするか。例: 20",
    )
    parser.add_argument(
        "--to-min",
        type=int,
        default=40,
        help="発走何分前まで通知対象にするか。例: 40",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="LINE送信せず表示だけ",
    )
    parser.add_argument(
        "--no-schedule",
        action="store_true",
        help="開催一覧を使わず、従来通りplace×raceで確認する",
    )

    args = parser.parse_args()

    date = args.date.replace("-", "")
    place_codes = normalize_places(args.places)
    race_nos = parse_races(args.races)
    use_schedule = not args.no_schedule

    conn = connect()

    checked = 0
    no_time_skipped = 0
    time_skipped = 0
    heavy_checked = 0
    sent = 0

    for item in iter_target_races(date, place_codes, race_nos, use_schedule=use_schedule):
        checked += 1

        race_id = item.get("race_id")
        place = item.get("place") or str(race_id)[4:6]
        place_name = item.get("place_name") or PLACES.get(place, place)

        try:
            race_no = item.get("race_no") or int(str(race_id)[-2:])
        except Exception:
            race_no = 0

        try:
            # Light step: get race info/time only.
            race_info = build_race_info_for_time_check(race_id, item, date)

            # Priority 1: if start time cannot be parsed, do not run heavy evaluation.
            if not has_start_time(race_info):
                no_time_skipped += 1
                print(f"SKIP NO TIME {race_id}: {place_name}{race_no}R 発走時刻を取得できません")
                continue

            # Only races inside the window go to heavy evaluation.
            if not should_check_now(
                race_info,
                date,
                from_min=args.from_min,
                to_min=args.to_min,
            ):
                time_skipped += 1
                print(f"SKIP TIME {race_id}: {place_name}{race_no}R 通知時間外")
                continue

            heavy_checked += 1

            # Heavy step: shutuba, odds, past runs, AI judgment.
            result = evaluate_race(race_id, date, args.budget)

            if result.mode not in ["official", "light"]:
                print(f"SKIP {race_id}: {result.title} / {result.reason}")
                continue

            if result.mode == "light" and not args.include_light:
                print(f"SKIP LIGHT {race_id}: 軽め勝負は通知対象外")
                continue

            if already_notified(conn, result.notify_key):
                print(f"SKIP DUP {race_id}: 通知済み")
                continue

            text = build_line_text(result, label=f"地方 {place_name}")

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
                sent += 1
                print(f"SENT {race_id}: {result.title}")

        except Exception as e:
            print(f"ERROR place={place} race={race_no} race_id={race_id}: {e}")

    print(
        "SUMMARY "
        f"checked={checked} "
        f"no_time_skipped={no_time_skipped} "
        f"time_skipped={time_skipped} "
        f"heavy_checked={heavy_checked} "
        f"sent={sent}"
    )


if __name__ == "__main__":
    main()

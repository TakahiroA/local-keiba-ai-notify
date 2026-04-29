import re
from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo

from features import enrich_horses
from model import (
    allocate_bets,
    build_candidate_bets,
    build_score,
    classify_bets,
    odds_sanity_check,
    rates,
)
from scraper import get_horses, get_race_info

JST = ZoneInfo("Asia/Tokyo")


@dataclass
class ShobuResult:
    race_id: str
    mode: str              # official / light / skip / error
    title: str
    reason: str
    race_name: str
    race_info_text: str
    axis_num: str = ""
    axis_name: str = ""
    axis_odds: float | None = None
    axis_prob: float = 0.0
    confidence: float = 0.0
    gap: float = 0.0
    data_rate: float = 0.0
    odds_rate: float = 0.0
    allocations: list | None = None

    @property
    def notify_key(self) -> str:
        return f"{self.race_id}:{self.mode}:{self.axis_num}"


def _race_time_today(race_info: dict, target_date: str) -> datetime | None:
    """race_info内の 12:30 のような時刻を拾ってJST datetimeにする。拾えない場合はNone。"""
    text = f"{race_info.get('name','')} {race_info.get('info','')}"
    m = re.search(r"(\d{1,2})[:：](\d{2})", text)
    if not m:
        return None
    ymd = str(target_date).replace("-", "")
    if len(ymd) != 8:
        return None
    return datetime(
        int(ymd[:4]), int(ymd[4:6]), int(ymd[6:8]),
        int(m.group(1)), int(m.group(2)), tzinfo=JST
    )


def should_check_now(race_info: dict, target_date: str, *, from_min: int = 15, to_min: int = 60) -> bool:
    """発走前 from_min〜to_min 分の範囲だけ通知判定する。時刻不明なら判定する。"""
    dt = _race_time_today(race_info, target_date)
    if dt is None:
        return True
    now = datetime.now(JST)
    mins = (dt - now).total_seconds() / 60
    return from_min <= mins <= to_min


def evaluate_race(race_id: str, target_date: str, budget: int = 3000) -> ShobuResult:
    race_info = get_race_info(race_id)
    race_info["target_date"] = target_date

    horses = get_horses(race_id)
    if len(horses) < 5:
        return ShobuResult(race_id, "skip", "見送り", "頭数不足です", race_info.get("name", ""), race_info.get("info", ""))

    horses = enrich_horses(horses, race_info)
    horses = build_score(horses, race_info)

    axis, second = horses[0], horses[1]
    gap = axis.get("score", 0) - second.get("score", 0)
    data_rate, odds_rate = rates(horses)
    axis_prob, second_prob = axis.get("prob", 0), second.get("prob", 0)
    prob_gap = max(0, axis_prob - second_prob)
    relative_score_gap = gap / max(axis.get("score", 0), 1e-9)
    confidence = min(
        0.95,
        axis_prob * 2.5
        + prob_gap * 3.0
        + relative_score_gap * 0.15
        + axis.get("stability", 0.5) * 0.10
        + data_rate * 0.10
        + odds_rate * 0.10,
    )

    base_kwargs = dict(
        race_id=race_id,
        race_name=race_info.get("name", ""),
        race_info_text=race_info.get("info", ""),
        axis_num=str(axis.get("num", "")),
        axis_name=str(axis.get("name", "")),
        axis_odds=axis.get("odds"),
        axis_prob=axis.get("prob", 0),
        confidence=confidence,
        gap=gap,
        data_rate=data_rate,
        odds_rate=odds_rate,
    )

    if data_rate == 0:
        return ShobuResult(mode="error", title="情報取得エラー", reason="過去走データが0件です", allocations=[], **base_kwargs)
    if data_rate < 0.70:
        return ShobuResult(mode="skip", title="見送り", reason="過去走データ不足です", allocations=[], **base_kwargs)

    ok, reason = odds_sanity_check(horses)
    if odds_rate == 0:
        return ShobuResult(mode="skip", title="見送り", reason="オッズを1頭も取得できていません", allocations=[], **base_kwargs)
    if not ok:
        return ShobuResult(mode="skip", title="見送り", reason=reason, allocations=[], **base_kwargs)
    if odds_rate < 0.80:
        return ShobuResult(mode="skip", title="見送り", reason="オッズ取得率が80%未満です", allocations=[], **base_kwargs)
    if confidence < 0.35:
        return ShobuResult(mode="skip", title="見送り", reason="軸の信頼度が低いです", allocations=[], **base_kwargs)

    partners = [h for h in horses[1:7] if h.get("odds") is not None][:5]
    if len(partners) < 2 or axis.get("odds") is None:
        return ShobuResult(mode="skip", title="見送り", reason="軸または相手のオッズ不足です", allocations=[], **base_kwargs)

    candidates = build_candidate_bets(axis, partners)
    official_bets, light_bets = classify_bets(candidates, axis, gap, confidence)

    if official_bets:
        allocations = allocate_bets(official_bets, budget, "official")
        return ShobuResult(mode="official", title="勝負レース", reason="買い条件を満たす馬券があります", allocations=allocations, **base_kwargs)

    if light_bets:
        allocations = allocate_bets(light_bets, budget, "light")
        return ShobuResult(mode="light", title="軽め勝負", reason="妙味はあるが軸信頼度は中程度です", allocations=allocations, **base_kwargs)

    return ShobuResult(mode="skip", title="見送り", reason="買い条件を満たす馬券がありません", allocations=[], **base_kwargs)


def build_line_text(result: ShobuResult, *, label: str = "地方") -> str:
    icon = "🔥" if result.mode == "official" else "⚠️"
    odds = "未取得" if result.axis_odds is None else f"{result.axis_odds:.1f}倍"
    lines = [
        f"{icon} {label}AI {result.title}",
        "",
        f"race_id: {result.race_id}",
        result.race_name or "レース名未取得",
        result.race_info_text or "",
        "",
        f"◎ {result.axis_num} {result.axis_name}",
        f"単勝: {odds}",
        f"想定勝率: {result.axis_prob * 100:.1f}%",
        f"信頼度: {result.confidence:.3f}",
        f"1位-2位差: {result.gap:.3f}",
        f"データ: 過去走{result.data_rate*100:.0f}% / オッズ{result.odds_rate*100:.0f}%",
        "",
        "推奨馬券:",
    ]

    if result.allocations:
        for bet, amount in result.allocations:
            lines.append(f"・{bet['type']} {bet['target']} {amount}円")
            lines.append(f"  {bet['names']} / EV {bet['ev']:.2f}")
    else:
        lines.append("・なし")

    lines.append("")
    lines.append("※最終オッズ・馬体重・取消は購入前に確認")
    return "\n".join([x for x in lines if x is not None])

import random
import re
import time
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

NAR_BASE_URL = "https://nar.netkeiba.com"
NAR_SP_BASE_URL = "https://nar.sp.netkeiba.com"
DB_URL = "https://db.netkeiba.com"
EN_URL = "https://en.netkeiba.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Referer": "https://nar.netkeiba.com/",
}

session = requests.Session()
session.headers.update(HEADERS)


def decode_html(content: bytes) -> str:
    """netkeiba系ページの文字化けを避けるための簡易判定。

    旧版は euc-jp を先に試していたため、UTF-8の地方netkeibaを
    euc-jpとして誤デコードし、レース名が「����」になることがあった。
    """
    candidates = []
    for enc in ["utf-8", "cp932", "euc-jp"]:
        try:
            s = content.decode(enc)
            # 日本語ページらしさ + 文字化けの少なさで採点
            score = 0
            score += s.count("競馬") * 5
            score += s.count("出馬") * 5
            score += s.count("レース") * 3
            score += s.count("地方") * 3
            score -= s.count("�") * 20
            score -= s.count("����") * 50
            candidates.append((score, enc, s))
        except Exception:
            pass

    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][2]

    return content.decode("utf-8", errors="replace")


def make_driver() -> webdriver.Chrome:
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1400,1200")
    options.add_argument(f"--user-agent={HEADERS['User-Agent']}")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)


def soup_from_selenium(url: str, wait: float = 3.0) -> Optional[BeautifulSoup]:
    driver = None
    try:
        print("Seleniumアクセス:", url)
        driver = make_driver()
        driver.get(url)
        time.sleep(wait)
        html = driver.page_source or ""
        if len(html) < 1000:
            print("Selenium HTMLが短すぎます:", len(html))
            return None
        return BeautifulSoup(html, "html.parser")
    except Exception as e:
        print("Seleniumエラー:", e)
        return None
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass


def repair_mojibake(s: str) -> str:
    """UTF-8/CP932/EUC-JPの誤変換で壊れた日本語をできる範囲で戻す。"""
    if not s:
        return s

    # UTF-8をlatin1/cp1252系で誤読した文字列はこの変換で戻ることがある。
    candidates = [s]
    for enc in ["latin1", "cp1252"]:
        try:
            candidates.append(s.encode(enc, errors="ignore").decode("utf-8", errors="ignore"))
        except Exception:
            pass

    # UTF-8をcp932/euc-jpで誤読した場合への保険。
    for enc1 in ["cp932", "euc-jp"]:
        for enc2 in ["utf-8", "cp932", "euc-jp"]:
            try:
                candidates.append(s.encode(enc1, errors="ignore").decode(enc2, errors="ignore"))
            except Exception:
                pass

    def score(x):
        jp = len(re.findall(r"[ぁ-んァ-ヶ一-龥]", x))
        bad = x.count("�") + len(re.findall(r"[ĒÆĮČĻÉ½ÅøõćÄ·īĘü]", x))
        return jp * 10 - bad * 20 + len(x) * 0.001

    return max(candidates, key=score)


def fetch(url: str, retry: int = 3, selenium_fallback: bool = False) -> Optional[BeautifulSoup]:
    for i in range(retry):
        time.sleep(random.uniform(0.4, 1.0))
        try:
            print("アクセス:", url)
            res = session.get(url, timeout=25)
            print("status:", res.status_code)

            if res.status_code == 200:
                if "nar.netkeiba.com" in url or "nar.sp.netkeiba.com" in url:
                    # NARページは環境により文字コード判定が暴れるため、候補を全部作って日本語量で選ぶ。
                    candidates = []
                    for enc in ["utf-8", "euc-jp", "cp932", "shift_jis"]:
                        try:
                            html = res.content.decode(enc, errors="replace")
                            html = repair_mojibake(html)
                            candidates.append(html)
                        except Exception:
                            pass

                    def html_score(h):
                        jp = len(re.findall(r"[ぁ-んァ-ヶ一-龥]", h))
                        bad = h.count("�") + len(re.findall(r"[ĒÆĮČĻÉ½ÅøõćÄ·īĘü]", h))
                        key = h.count("出馬") + h.count("競馬") + h.count("レース") + h.count("馬場")
                        return jp + key * 50 - bad * 100

                    if candidates:
                        html = max(candidates, key=html_score)
                        if len(html) >= 1000:
                            return BeautifulSoup(html, "html.parser")

                enc = res.apparent_encoding or res.encoding or ""
                if enc:
                    try:
                        html = res.content.decode(enc, errors="replace")
                        html = repair_mojibake(html)
                        if len(html) >= 1000:
                            return BeautifulSoup(html, "html.parser")
                    except Exception:
                        pass

                html = decode_html(res.content)
                html = repair_mojibake(html)
                if len(html) >= 1000:
                    return BeautifulSoup(html, "html.parser")
                print("HTMLが短すぎます:", len(html))

            if res.status_code in [403, 429, 500, 502, 503, 504]:
                time.sleep(2 + i * 2)
        except Exception as e:
            print("通信エラー:", e)
        time.sleep(1 + i)

    if selenium_fallback:
        return soup_from_selenium(url)
    return None



def clean_name(name: str) -> str:
    if not name:
        return ""
    name = name.strip()
    for s in ["のデータベース", " | 競走馬データ", "競走馬データ", "出馬表", "地方競馬レース情報"]:
        name = name.replace(s, "")
    name = re.sub(r"\s+", " ", name)
    return name.strip(" |｜-　")


def normalize_race_id(value: str) -> str:
    value = str(value or "").strip()
    m = re.search(r"race_id=(\d{12})", value)
    if m:
        return m.group(1)
    m = re.search(r"\b(\d{12})\b", value)
    return m.group(1) if m else value


def horse_id_from_url(url: str) -> str:
    m = re.search(r"/horse/(?:result/)?(\d+)", url or "")
    return m.group(1) if m else ""


def normalize_horse_url(href: str) -> str:
    if not href:
        return ""
    m = re.search(r"/horse/(\d+)", href)
    if m:
        return f"{DB_URL}/horse/{m.group(1)}/"
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return urljoin(DB_URL, href)
    return href


def safe_float(text) -> Optional[float]:
    try:
        text = str(text).strip().replace(",", "").replace("倍", "")
        if text in ["", "---", "---.-", "-", "取消", "除外"]:
            return None
        m = re.search(r"\d+(?:\.\d+)?", text)
        return float(m.group(0)) if m else None
    except Exception:
        return None


def parse_rank(text) -> Optional[int]:
    text = str(text).strip()
    if text in ["", "-", "--", "除外", "取消", "中止", "失格"]:
        return None
    m = re.search(r"\d+", text)
    if not m:
        return None
    v = int(m.group(0))
    return v if 1 <= v <= 18 else None


def race_id_from_date_place(date: str, place: str, race_no: int) -> str:
    date = str(date).replace("-", "")
    return f"{date[:4]}{str(place).zfill(2)}{date[4:8]}{int(race_no):02d}"


def race_url(race_id: str, kind: str = "shutuba", sp: bool = False) -> str:
    base = NAR_SP_BASE_URL if sp else NAR_BASE_URL
    if kind == "odds":
        return f"{base}/odds/index.html?race_id={race_id}&type=b1"
    return f"{base}/race/{kind}.html?race_id={race_id}"


def page_looks_like_race(soup: BeautifulSoup, race_no: Optional[int] = None) -> bool:
    if soup is None:
        return False
    text = soup.get_text(" ", strip=True)
    if "該当するレースがありません" in text or "ページが見つかりません" in text:
        return False
    if "出馬表" in text and ("オッズ" in text or "馬券" in text or "地方競馬" in text):
        if race_no is None:
            return True
        return f"{int(race_no)}R" in text or f"{int(race_no)} R" in text
    return False


def find_race_id(date: str, place: str, race_no: int) -> Optional[str]:
    """地方netkeibaのrace_idを作る。

    地方netkeibaは多くのページで YYYY + 場コード + MMDD + RR の12桁。
    まず直接候補を検証し、ダメならレース一覧からrace_idを拾う。
    """
    candidate = race_id_from_date_place(date, place, race_no)

    for url in [race_url(candidate), race_url(candidate, sp=True)]:
        soup = fetch(url, retry=1, selenium_fallback=False)
        if page_looks_like_race(soup, race_no):
            print("確定:", candidate)
            return candidate

    list_urls = [
        f"{NAR_BASE_URL}/top/race_list.html?kaisai_date={date}",
        f"{NAR_SP_BASE_URL}/top/race_list.html?kaisai_date={date}",
        f"{NAR_BASE_URL}/top/?kaisai_date={date}",
    ]
    for url in list_urls:
        soup = fetch(url, retry=1, selenium_fallback=True)
        if soup is None:
            continue
        links = soup.select("a[href*='race_id=']")
        for a in links:
            href = a.get("href", "")
            m = re.search(r"race_id=(\d{12})", href)
            if not m:
                continue
            rid = m.group(1)
            if rid[4:6] == str(place).zfill(2) and rid[-2:] == f"{int(race_no):02d}":
                print("一覧から確定:", rid)
                return rid

    # ページ検証に失敗しても、race_id規則はかなり安定しているため最後に候補を返す。
    print("検証失敗。候補race_idを使用:", candidate)
    return candidate


def extract_place_from_race_id(race_id: str) -> str:
    code = str(race_id)[4:6] if len(str(race_id)) >= 6 else ""
    return {
        "30": "門別", "35": "盛岡", "36": "水沢", "42": "浦和", "43": "船橋",
        "44": "大井", "45": "川崎", "46": "金沢", "47": "笠松", "48": "名古屋",
        "50": "園田", "51": "姫路", "54": "高知", "55": "佐賀", "65": "帯広ば",
    }.get(code, "")


def get_race_info(race_id: str) -> dict:
    urls = [race_url(race_id), race_url(race_id, sp=True)]
    for url in urls:
        soup = fetch(url, retry=2, selenium_fallback=True)
        if soup is None:
            continue

        race_name = soup.select_one(".RaceName, .RaceName_main, h1")
        race_data = soup.select_one(".RaceData01, .RaceData, .RaceData_Item")
        name = clean_name(race_name.get_text(" ", strip=True)) if race_name else ""
        info = race_data.get_text(" ", strip=True) if race_data else ""

        if not name:
            title = soup.select_one("title")
            name = clean_name(title.get_text(" ", strip=True)) if title else ""

        text = info + " " + soup.get_text(" ", strip=True)
        place_name = extract_place_from_race_id(race_id)
        if not place_name:
            for p in ["門別","盛岡","水沢","浦和","船橋","大井","川崎","金沢","笠松","名古屋","園田","姫路","高知","佐賀","帯広"]:
                if p in text:
                    place_name = p
                    break

        surface = "ダート"
        if "芝" in text:
            surface = "芝"
        if "障" in text:
            surface = "障害"

        distance = 0
        m = re.search(r"(芝|ダ|ダート|右|左)?\s*([0-9]{3,4})m", text)
        if m:
            distance = int(m.group(2))

        ground = "良"
        if "不良" in text:
            ground = "不良"
        elif "稍重" in text or "稍" in text:
            ground = "稍重"
        elif "重" in text:
            ground = "重"

        if name or info:
            return {
                "name": name,
                "info": info,
                "distance": distance,
                "ground": ground,
                "surface": surface,
                "place_name": place_name,
            }

    return {
        "name": "",
        "info": "",
        "distance": 0,
        "ground": "良",
        "surface": "ダート",
        "place_name": extract_place_from_race_id(race_id),
    }


def extract_horse_number(cols, row) -> str:
    tag = row.select_one(".Umaban, [class*='Umaban'], .HorseNumber, [class*='HorseNumber']")
    if tag:
        v = parse_rank(tag.get_text(strip=True))
        if v is not None:
            return str(v)
    for col in cols[:4]:
        text = col.get_text(strip=True)
        if re.fullmatch(r"\d{1,2}", text):
            return text
    return ""


def find_header_index(headers: List[str], candidates: List[str]) -> Optional[int]:
    for cand in candidates:
        for i, h in enumerate(headers):
            if cand in h:
                return i
    return None


def horse_link_candidates(soup: BeautifulSoup):
    """出馬表内の馬リンク候補を広めに拾う。

    地方netkeibaはPC/SPや開催でHTML構造が変わるため、
    table行だけに依存しない。
    """
    links = []
    for a in soup.select("a[href*='/horse/']"):
        href = a.get("href", "")
        name = clean_name(a.get_text(" ", strip=True))
        if not href or not name:
            continue
        if not re.search(r"/horse/\d+", href):
            continue
        # DB内のパンくずや広告由来のリンクを弱く除外
        if len(name) <= 1:
            continue
        links.append(a)
    return links


def nearest_container_for_horse(link):
    for tag_name in ["tr", "li"]:
        parent = link.find_parent(tag_name)
        if parent is not None:
            return parent
    # div構造のSP版対策。近すぎるa自身ではなく、数階層上まで見る。
    parent = link
    for _ in range(5):
        parent = parent.parent
        if parent is None:
            break
        text = parent.get_text(" ", strip=True)
        if "騎手" in text or "斤量" in text or "オッズ" in text or len(text) > 20:
            return parent
    return link.parent or link


def extract_first_number(text: str) -> str:
    m = re.search(r"(?<!\d)([1-9]|1[0-8])(?!\d)", str(text or ""))
    return m.group(1) if m else ""



def is_scratched_text(text: str) -> bool:
    text = str(text or "")
    return any(key in text for key in ["取消", "除外", "競走除外", "出走取消", "発売対象外"])


def looks_like_race_horse_row(row_text: str, name: str) -> bool:
    """出馬表以外の関連記事・ランキング内の馬リンクを弾く。"""
    row_text = str(row_text or "")
    if not name or name not in row_text:
        return False

    bad_words = [
        "お気に入り", "ニュース", "コラム", "予想", "掲示板", "データベース",
        "血統", "産駒", "検索", "ランキング", "AI", "netkeiba",
    ]
    if any(w in row_text for w in bad_words) and not any(w in row_text for w in ["騎手", "斤量", "馬番", "単勝", "人気", "枠"]):
        return False

    # 出馬表の1行ならだいたい馬番・斤量・騎手・性齢・人気などのどれかを含む。
    good = ["騎手", "斤量", "馬番", "単勝", "人気", "牡", "牝", "セ", "枠", "kg"]
    return any(w in row_text for w in good) or len(row_text) <= 120


def extract_status(row_text: str) -> str:
    if "取消" in row_text or "出走取消" in row_text:
        return "取消"
    if "除外" in row_text or "競走除外" in row_text:
        return "除外"
    return "出走"


def parse_horses_from_shutuba(soup: BeautifulSoup) -> List[dict]:
    horses = []
    seen = set()

    rows = []
    row_selectors = [
        "table.Shutuba_Table tr",
        "table.RaceTable01 tr",
        "tr.HorseList",
        "tr[class*='HorseList']",
        "tr",
    ]
    for sel in row_selectors:
        for row in soup.select(sel):
            if row not in rows:
                rows.append(row)

    containers = []
    for row in rows:
        if row.select_one("a[href*='/horse/']"):
            containers.append(row)

    if len(containers) < 4:
        containers = []
        for link in horse_link_candidates(soup):
            c = nearest_container_for_horse(link)
            if c not in containers:
                containers.append(c)

    for idx, row in enumerate(containers, 1):
        link = row.select_one("a[href*='/horse/']")
        if not link:
            continue

        href = link.get("href", "")
        name = clean_name(link.get_text(" ", strip=True))
        row_text = row.get_text(" ", strip=True)

        if not href or not name:
            continue

        if not looks_like_race_horse_row(row_text, name):
            continue

        status = extract_status(row_text)
        if status != "出走":
            print("出走取消/除外を除外:", name, status)
            continue

        hid = horse_id_from_url(href) or href
        if hid in seen:
            continue
        seen.add(hid)

        cols = row.find_all("td")
        texts = [c.get_text(" ", strip=True) for c in cols] if cols else []

        num = extract_horse_number(cols, row) if cols else ""
        if not num:
            before_name = row_text.split(name)[0] if name in row_text else row_text[:30]
            num = extract_first_number(before_name)
        # 馬番が取れない馬リンクは、出馬表外リンク混入の可能性が高いので除外する。
        # 旧版はidxから9,10,11...を自動採番してしまい、オッズ表に存在しない馬を混ぜていた。
        if not num:
            print("馬番不明の馬リンクを除外:", name)
            continue

        jockey = ""
        trainer = ""
        sex_age = ""
        weight = ""

        jockey_tag = row.select_one("a[href*='/jockey/'], .Jockey, [class*='Jockey']")
        trainer_tag = row.select_one("a[href*='/trainer/'], .Trainer, [class*='Trainer']")
        if jockey_tag:
            jockey = jockey_tag.get_text(" ", strip=True)
        if trainer_tag:
            trainer = trainer_tag.get_text(" ", strip=True)

        token_source = texts if texts else re.split(r"\s+", row_text)
        for t in token_source:
            if not sex_age and re.search(r"[牡牝セ騸]\s*\d+", t):
                sex_age = t
            if not weight and re.fullmatch(r"\d{2,3}(?:\.\d)?", t):
                weight = t

        if not jockey and len(cols) > 6:
            jockey = cols[6].get_text(" ", strip=True)
        if not trainer and len(cols) > 7:
            trainer = cols[7].get_text(" ", strip=True)
        if not sex_age and len(cols) > 4:
            sex_age = cols[4].get_text(" ", strip=True)
        if not weight and len(cols) > 5:
            weight = cols[5].get_text(" ", strip=True)

        horses.append({
            "num": num,
            "name": name,
            "horse_id": hid,
            "sex_age": sex_age,
            "weight": weight,
            "jockey": clean_name(jockey),
            "trainer": clean_name(trainer),
            "status": status,
            "odds": None,
            "odds_source": "未取得",
            "url": normalize_horse_url(href),
        })

    def sort_key(h):
        try:
            return int(h.get("num") or 999)
        except Exception:
            return 999

    horses.sort(key=sort_key)
    return horses



def parse_win_odds_from_table(table) -> Dict[str, float]:
    rows = table.select("tr")
    if not rows:
        return {}

    headers = [c.get_text(" ", strip=True) for c in rows[0].find_all(["th", "td"])]
    num_i = find_header_index(headers, ["馬番", "馬 番", "番"])
    odds_i = find_header_index(headers, ["単勝", "オッズ"])

    result: Dict[str, float] = {}
    for row in rows[1:]:
        row_text = row.get_text(" ", strip=True)
        if is_scratched_text(row_text):
            continue

        cols = row.find_all(["td", "th"])
        if len(cols) < 2:
            continue
        texts = [c.get_text(" ", strip=True) for c in cols]

        num = None
        if num_i is not None and num_i < len(texts):
            num = parse_rank(texts[num_i])
        if num is None:
            tag = row.select_one(".Umaban, [class*='Umaban'], .HorseNumber, [class*='HorseNumber']")
            if tag:
                num = parse_rank(tag.get_text(strip=True))
        if num is None:
            for t in texts[:3]:
                num = parse_rank(t)
                if num is not None:
                    break
        if num is None:
            continue

        odds = None
        if odds_i is not None and odds_i < len(texts):
            odds = safe_float(texts[odds_i])

        if odds is None:
            decimal_values = []
            for t in texts:
                for m in re.finditer(r"(?<!\d)(\d{1,3}\.\d)(?!\d)", t):
                    v = safe_float(m.group(1))
                    if v is not None and 1.0 <= v <= 999.9:
                        decimal_values.append(v)
            if decimal_values:
                # 単勝・複勝が並ぶ場合でも、通常は最初の小数が単勝。
                odds = decimal_values[0]

        if odds is not None and 1.0 <= odds <= 999.9:
            result[str(num)] = float(odds)

    return result



def get_win_odds(race_id: str) -> Dict[str, float]:
    """地方netkeibaから単勝オッズを馬番ごとに取得する。

    実オッズページが未公開・締切後・JS描画の場合は取得できないことがある。
    その場合は空dictを返し、予想側では暫定評価に落とす。
    """
    urls = [
        race_url(race_id, "odds"),
        f"{NAR_BASE_URL}/odds/odds.html?race_id={race_id}&type=b1",
        f"{NAR_SP_BASE_URL}/odds/odds.html?race_id={race_id}&type=b1",
        f"{NAR_BASE_URL}/race/odds.html?race_id={race_id}&type=b1",
    ]

    best: Dict[str, float] = {}
    for url in urls:
        soup = fetch(url, retry=2, selenium_fallback=True)
        if soup is None:
            continue

        odds_map: Dict[str, float] = {}
        for table in soup.select("table"):
            parsed = parse_win_odds_from_table(table)
            if len(parsed) > len(odds_map):
                odds_map = parsed

        # tableで拾えない場合の保険。テキスト中の「馬番 馬名 単勝」風の並びを弱く拾う。
        if not odds_map:
            text = soup.get_text(" ", strip=True)
            pattern = re.compile(r"(?:^|\s)([1-9]|1[0-8])\s+([^\d\s]{2,})\s+(\d{1,3}\.\d)(?=\s)")
            for m in pattern.finditer(text):
                odds = safe_float(m.group(3))
                if odds is not None and 1.0 <= odds <= 999.9:
                    odds_map[m.group(1)] = odds

        if len(odds_map) > len(best):
            best = odds_map
        if len(best) >= 8:
            break

    print("単勝オッズ取得:", len(best), best)
    return best


def get_horses(race_id: str) -> List[dict]:
    urls = [race_url(race_id), race_url(race_id, sp=True)]
    best_horses: List[dict] = []

    for url in urls:
        soup = fetch(url, retry=2, selenium_fallback=True)
        if soup is None:
            continue
        parsed = parse_horses_from_shutuba(soup)
        print("出馬表候補:", url, len(parsed), [(h.get("num"), h.get("name")) for h in parsed])
        if len(parsed) > len(best_horses):
            best_horses = parsed

    horses = best_horses

    if not horses:
        print("取得馬数:", 0)
        return []

    odds_map = get_win_odds(race_id)

    horse_nums = {str(h.get("num", "")) for h in horses}
    missing_nums = [str(h.get("num", "")) for h in horses if str(h.get("num", "")) not in odds_map]
    extra_odds = [n for n in odds_map.keys() if n not in horse_nums]

    if odds_map and len(horses) != len(odds_map):
        print("注意: 出馬表頭数と単勝オッズ数が一致しません",
              "horses=", len(horses), "odds=", len(odds_map),
              "missing_odds_nums=", missing_nums,
              "extra_odds_nums=", extra_odds)

    # オッズ表が十分取れていて、出馬表側だけ余分な馬番を持つ場合は、出馬表外リンク混入とみなして除外。
    # ただしオッズがほとんど取れていない場合は、無理に削らない。
    if odds_map and len(odds_map) >= 5 and missing_nums and not extra_odds:
        before = len(horses)
        horses = [h for h in horses if str(h.get("num", "")) in odds_map]
        dropped = before - len(horses)
        if dropped:
            print("オッズ表に存在しない馬番を除外:", missing_nums, "除外数=", dropped)

    for h in horses:
        num = str(h.get("num", ""))
        h["odds"] = odds_map.get(num)
        h["odds_source"] = "単勝オッズページ" if h["odds"] is not None else "未取得"

    print("取得馬数:", len(horses), [(h.get("num"), h.get("name"), h.get("odds")) for h in horses])
    return horses



def to_float(text) -> Optional[float]:
    try:
        text = str(text).strip().replace(",", "")
        m = re.search(r"[0-9]+(?:\.[0-9]+)?", text)
        return float(m.group(0)) if m else None
    except Exception:
        return None


def parse_passing(text) -> int:
    nums = re.findall(r"\d+", str(text or ""))
    if not nums:
        return 8
    try:
        return int(nums[0])
    except Exception:
        return 8


def parse_distance(text) -> Optional[int]:
    if not text:
        return None
    m = re.search(r"(芝|ダ|ダート|障)?\s*([0-9]{3,4})", str(text))
    if not m:
        return None
    try:
        return int(m.group(2))
    except Exception:
        return None


def parse_date_int(text) -> Optional[int]:
    text = str(text or "").strip()
    if not text:
        return None

    m = re.search(r"(20\d{2})[./\-年]\s*(\d{1,2})[./\-月]\s*(\d{1,2})", text)
    if m:
        y, mo, d = map(int, m.groups())
        return y * 10000 + mo * 100 + d

    m = re.search(r"(?<!\d)(\d{2})[./\-](\d{1,2})[./\-](\d{1,2})(?!\d)", text)
    if m:
        y, mo, d = map(int, m.groups())
        y += 2000 if y < 70 else 1900
        return y * 10000 + mo * 100 + d

    for fmt in ["%b %d, %Y", "%B %d, %Y", "%b %d %Y", "%B %d %Y"]:
        try:
            dt = datetime.strptime(text[:20].replace("  ", " "), fmt)
            return dt.year * 10000 + dt.month * 100 + dt.day
        except Exception:
            pass

    return None


def get_past_run_urls(horse_url: str) -> List[str]:
    horse_url = normalize_horse_url(horse_url)
    hid = horse_id_from_url(horse_url)
    urls = []
    if hid:
        urls.extend([
            f"{DB_URL}/horse/{hid}/",
            f"{DB_URL}/horse/result/{hid}/",
            f"{EN_URL}/db/horse/result/{hid}/",
            f"{EN_URL}/db/horse/{hid}/",
        ])
    if horse_url and horse_url not in urls:
        urls.insert(0, horse_url)
    return urls


def find_past_run_table(soup: BeautifulSoup):
    table = soup.select_one("table.db_h_race_results")
    if table is not None:
        return table
    for table in soup.select("table"):
        text = table.get_text(" ", strip=True)
        if (("日付" in text and "着順" in text and "距離" in text) or
                ("Date" in text and ("Finish" in text or "Fin" in text) and "Distance" in text)):
            return table
    return None


def get_past_runs(horse_url: str, target_date: Optional[str] = None) -> List[dict]:
    if not horse_url:
        return []

    target_date_int = parse_date_int(target_date) if target_date else None

    for url in get_past_run_urls(horse_url):
        soup = fetch(url, retry=2, selenium_fallback=True)
        if soup is None:
            continue
        table = find_past_run_table(soup)
        if table is None:
            print("過去走テーブルなし:", url)
            continue

        rows = table.select("tr")
        if len(rows) <= 1:
            continue
        headers = [c.get_text(strip=True) for c in rows[0].find_all(["th", "td"])]

        date_i = find_header_index(headers, ["日付", "Date"])
        rank_i = find_header_index(headers, ["着順", "着", "Finish", "Fin"])
        distance_i = find_header_index(headers, ["距離", "Distance"])
        passing_i = find_header_index(headers, ["通過", "Corner", "Position"])
        agari_i = find_header_index(headers, ["上り", "上がり", "Last", "3F"])

        runs = []
        for row in rows[1:]:
            cols = row.find_all("td")
            if len(cols) < 5:
                continue
            texts = [c.get_text(" ", strip=True) for c in cols]

            run_date = parse_date_int(texts[date_i]) if date_i is not None and date_i < len(texts) else None
            if run_date is None:
                for t in texts[:4]:
                    run_date = parse_date_int(t)
                    if run_date is not None:
                        break

            # 未来情報漏れ防止。
            if target_date_int is not None:
                if run_date is None or run_date >= target_date_int:
                    continue

            rank = parse_rank(texts[rank_i]) if rank_i is not None and rank_i < len(texts) else None
            distance = parse_distance(texts[distance_i]) if distance_i is not None and distance_i < len(texts) else None
            passing = texts[passing_i] if passing_i is not None and passing_i < len(texts) else ""
            agari = to_float(texts[agari_i]) if agari_i is not None and agari_i < len(texts) else None

            if rank is None:
                for t in texts[:8]:
                    rank = parse_rank(t)
                    if rank is not None:
                        break
            if distance is None:
                for t in texts:
                    distance = parse_distance(t)
                    if distance is not None:
                        break
            if agari is None:
                for t in reversed(texts):
                    v = to_float(t)
                    if v is not None and 30.0 <= v <= 45.0:
                        agari = v
                        break
            if rank is None:
                continue

            runs.append({
                "date": run_date,
                "rank": rank,
                "agari": agari,
                "distance": distance,
                "first_pos": parse_passing(passing),
            })
            if len(runs) >= 8:
                break

        if runs:
            print("過去走取得:", len(runs), url)
            return runs

    return []

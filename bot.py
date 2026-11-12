# ==========================================
# МХБ & COMEX ӨДРИЙН АРИЛЖААНЫ ТОЙМ - TELEGRAM BOT (БҮРЭН ЭХ КОД)
# Шинэчлэгдсэн mseSessionToken + Next-Action (42 char) + 21 MSE Endpoint + COMEX
# ==========================================

import os
import requests
import json
import re
import io
import urllib3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import squarify
from datetime import datetime
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from urllib.parse import urljoin

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# 1. ТОХИРГОО БОЛОН ШИНЭЧЛЭГДСЭН ПАРАМЕТРҮҮД
# ==========================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL = os.getenv("CHANNEL", "@openburry")

plt.rcParams["font.family"] = "DejaVu Sans"

MSE_BASE_URL = "https://mse.mn"
MSE_URL = "https://mse.mn/todays-trade"
MSE_SETTINGS_URL = "https://mse.mn/api/public/settings"
MSE_SESSION_TOKEN_URL = "https://mse.mn/api/auth/session-token"
COMEX_BASE_URL = "https://comex.mse.mn"

# Таны cURL-ээс авсан шинэ 42 тэмдэгттэй next-action хэш
DEFAULT_NEXT_ACTION = os.getenv(
    "MSE_NEXT_ACTION",
    "7f15ecc768683d85b3e8f80304cb1bba603ff76b3e"
)

# Таны cURL-ээс авсан шинэчлэгдсэн next-router-state-tree
NEXT_ROUTER_STATE_TREE = (
    "%5B%22%22%2C%7B%22children%22%3A%5B%22(navbar)%22%2C%7B%22children%22%3A%5B"
    "%22(trade)%22%2C%7B%22children%22%3A%5B%22todays-trade%22%2C%7B%22children%22%3A%5B"
    "%22__PAGE__%22%2C%7B%7D%2Cnull%2Cnull%5D%7D%2Cnull%2Cnull%5D%7D%2Cnull%2Cnull%5D%7D"
    "%2Cnull%2Cnull%5D%7D%2Cnull%2Cnull%2Ctrue%5D"
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/157.0.0.0 Safari/537.36"
)

SEC_CH_UA = '"Not-A.Brand";v="99", "Google Chrome";v="157", "Chromium";v="157"'

BROWSER_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,mn;q=0.8",
    "User-Agent": USER_AGENT,
}

# Анхны суурь Cookie (сесс эхлэхэд шинэчлэгдэнэ)
INITIAL_COOKIES = {
    "_ga": "GA1.1.880138786.1757978109",
    "_ga_4JVXGPBK2L": "GS2.1.s1789177239$o399$g1$t1789177252$j47$l0$h0",
    "twk_uuid_63cf736547425128790f4ccf": (
        "%7B%22uuid%22%3A%221.MSPsb2oEazmyvFvbtbNskGiR8804FNrb0jHm1K9kkWOvva2uryRbfbvf8HSoKUAnD7QxdZGcRaWLlXmdlekf1mb1ISNsBnoAT9WNjuWfMmLGI"
        "%22%2C%22version%22%3A3%2C%22domain%22%3A%22mse.mn%22%2C%22ts%22%3A1790082249434%7D"
    ),
    "mseSessionToken": os.getenv(
        "MSE_SESSION_TOKEN",
        "v1.eyJmcCI6ImYwZTJiOTI1Mzc3MTUxYzYiLCJpcCI6IjY0LjExOS4yMS4xMTMiLCJpYXQiOjE3OTQ0OTU2NDM1MDMsImV4cCI6MTc5NDQ5OTI0MzUwMywianRpIjoiME9zTG9XMUszWUx1bmE3ZyJ9.QeAlnqxWEV-QB1CYzVPUJj_N7FBeiYuvEcQHpnFknEI"
    ),
}

def build_action_headers(next_action):
    return {
        "Accept": "text/x-component",
        "Accept-Language": "en-US,en;q=0.9,mn;q=0.8",
        "Connection": "keep-alive",
        "Content-Type": "text/plain;charset=UTF-8",
        "DNT": "1",
        "Origin": "https://mse.mn",
        "Referer": "https://mse.mn/todays-trade",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": USER_AGENT,
        "next-action": next_action,
        "next-router-state-tree": NEXT_ROUTER_STATE_TREE,
        "sec-ch-ua": SEC_CH_UA,
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    }

# ==========================================
# 2. MSE DATA & COUNT ENDPOINTS
# ==========================================

DATA_ENDPOINTS = [
    ("tradingStatus1", "Хувьцаат компанийн I ангилал", "MNT"),
    ("tradingStatus2", "Хувьцаат компанийн II ангилал", "MNT"),
    ("tradingStatus3", "Хувьцаат компанийн III ангилал", "MNT"),
    ("tradingXoc", "Хөрөнгө оруулалтын сан", "MNT"),
    ("tradingAbs", "Хөрөнгөөр баталгаажсан үнэт цаас", "MNT"),
    ("tradingStatusZG", "ЗГҮЦ хоёрдогч зах зээлийн арилжаа", "MNT"),
    ("tradingStatusXK", "Компанийн бондын хоёрдогч зах зээлийн арилжаа", "MNT"),
    ("tradingStatusUSD", "Компанийн бондын хоёрдогч зах зээл USD", "USD"),
    ("tradingBlock", "Багцын арилжаа", "MNT"),
    ("tradingBlockUSD", "Багцын арилжаа USD", "USD"),
    ("tradingAON", "AON арилжаа", "MNT"),
]

COUNT_ENDPOINTS = [
    ("tradingStatus1Count", "Хувьцаат компанийн I ангилал"),
    ("tradingStatus2Count", "Хувьцаат компанийн II ангилал"),
    ("tradingStatus3Count", "Хувьцаат компанийн III ангилал"),
    ("tradingXocCount", "Хөрөнгө оруулалтын сан"),
    ("tradingAbsCount", "Хөрөнгөөр баталгаажсан үнэт цаас"),
    ("tradingStatusZGCount", "ЗГҮЦ хоёрдогч зах зээлийн арилжаа"),
    ("tradingStatusXKCount", "Компанийн бондын хоёрдогч зах зээл"),
    ("tradingStatusUSDCount", "Компанийн бондын хоёрдогч зах зээл USD"),
    ("tradingBlockCount", "Багцын арилжаа"),
    ("tradingBlockUSDCount", "Багцын арилжаа USD"),
]

# ==========================================
# 3. ТООН УТГА ЦЭВЭРЛЭХ & RSC PARSER
# ==========================================

def to_number(value):
    if value is None:
        return 0.0
    if isinstance(value, (int, float, np.number)):
        return float(value)
    text = str(value).strip()
    if not text:
        return 0.0
    text = text.replace(",", "").replace(" ", "").replace("₮", "").replace("$", "")
    try:
        return float(text)
    except Exception:
        return 0.0

def parse_rsc_response(response_text):
    for line in response_text.splitlines():
        line = line.strip()
        if not line.startswith("1:"):
            continue
        json_part = line[2:].strip()
        try:
            return json.loads(json_part)
        except json.JSONDecodeError:
            try:
                decoder = json.JSONDecoder()
                obj, _ = decoder.raw_decode(json_part)
                return obj
            except Exception:
                pass
    return None

def call_mse_endpoint(session, endpoint, next_action, parameter="?lang=mn"):
    payload = json.dumps([
        {
            "url": endpoint,
            "parameter": parameter,
            "config": {"hasToken": False}
        }
    ])
    response = session.post(
        MSE_URL,
        headers=build_action_headers(next_action),
        data=payload,
        verify=False,
        timeout=30
    )
    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:300]}")
    parsed = parse_rsc_response(response.text)
    return response, parsed

# ==========================================
# 4. SESSION TOKEN & NEXT-ACTION АВТОМАТ ТОХИРУУЛГА
# ==========================================

def refresh_mse_session_token(session):
    """
    /api/public/settings болон /api/auth/session-token дуудаж
    тухайн серверийн IP дээр шинэ mseSessionToken cookie авна.
    """
    api_headers = {
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9,mn;q=0.8",
        "Connection": "keep-alive",
        "DNT": "1",
        "Origin": "https://mse.mn",
        "Referer": "https://mse.mn/todays-trade",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": USER_AGENT,
        "sec-ch-ua": SEC_CH_UA,
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    }

    try:
        session.get(MSE_SETTINGS_URL, headers=api_headers, verify=False, timeout=15)
    except Exception as e:
        print(f"   ⚠️ Settings дуудахад алдаа: {e}")

    try:
        post_headers = dict(api_headers)
        post_headers["Content-Type"] = "application/json"
        post_headers["Content-Length"] = "0"

        r = session.post(MSE_SESSION_TOKEN_URL, headers=post_headers, data="", verify=False, timeout=15)
        print(f"🔑 Session-Token API статус: {r.status_code}")

        # Хэрэв JSON дотор токен буцаасан бол cookie-д суулгах
        if r.status_code == 200 and r.text.strip().startswith("{"):
            try:
                data = r.json()
                token = (
                    data.get("mseSessionToken")
                    or data.get("token")
                    or data.get("sessionToken")
                    or (data.get("data") if isinstance(data.get("data"), str) else None)
                )
                if token and isinstance(token, str):
                    session.cookies.set("mseSessionToken", token, domain="mse.mn")
            except Exception:
                pass

        active_token = session.cookies.get("mseSessionToken")
        if active_token:
            print(f"   ✅ Идэвхтэй mseSessionToken: {active_token[:28]}...")
    except Exception as e:
        print(f"   ⚠️ Session-Token авахад алдаа: {e}")

def extract_chunks_from_webpack(webpack_js_text):
    chunk_urls = set()
    for m in re.findall(r'static/chunks/[^"\'\s\\]+\.js', webpack_js_text):
        chunk_urls.add(f"{MSE_BASE_URL}/_next/{m}")

    hash_pairs = re.findall(r'(?:"([^"]+)"|(\d+))\s*:\s*"([0-9a-f]{16})"', webpack_js_text)
    prefix_pairs = re.findall(r'(?:"([^"]+)"|(\d+))\s*:\s*"([^"]+)"', webpack_js_text)

    prefix_map = {}
    for k_str, k_num, val in prefix_pairs:
        key = k_str or k_num
        if not re.fullmatch(r'[0-9a-f]{16}', val) and len(val) < 120:
            prefix_map[key] = val

    for k_str, k_num, h in hash_pairs:
        key = k_str or k_num
        name = prefix_map.get(key, key)
        chunk_urls.add(f"{MSE_BASE_URL}/_next/static/chunks/{name}-{h}.js")
        chunk_urls.add(f"{MSE_BASE_URL}/_next/static/chunks/{name}.{h}.js")

    return chunk_urls

def discover_candidate_actions(session):
    """Хэрэв Next-Action дахин солигдвол JS chunk-уудаас 40-44 урттай хэшийг автоматаар хайх"""
    print("🔎 MSE сайтаас шинэ Next-Action хэш кодыг хайж байна...")
    chunk_urls = set()
    webpack_urls = set()

    probe_requests = [
        (MSE_URL, {"RSC": "1", "next-router-state-tree": NEXT_ROUTER_STATE_TREE, "User-Agent": USER_AGENT}),
        (MSE_BASE_URL, {"RSC": "1", "next-router-prefetch": "1", "next-url": "/todays-trade", "User-Agent": USER_AGENT}),
        (MSE_URL, BROWSER_HEADERS),
        (MSE_BASE_URL, BROWSER_HEADERS),
    ]

    for url, hdrs in probe_requests:
        try:
            r = session.get(url, headers=hdrs, verify=False, timeout=15)
            for m in re.findall(r'(?:_next/)?static/chunks/[^"\'\s<>\\]+\.js', r.text):
                clean_m = m if m.startswith("_next/") else f"_next/{m}"
                full_url = f"{MSE_BASE_URL}/{clean_m}"
                if "webpack-" in full_url:
                    webpack_urls.add(full_url)
                else:
                    chunk_urls.add(full_url)
        except Exception:
            pass

    for wp_url in webpack_urls:
        try:
            r = session.get(wp_url, headers=BROWSER_HEADERS, verify=False, timeout=15)
            if r.status_code == 200:
                chunk_urls.update(extract_chunks_from_webpack(r.text))
        except Exception:
            pass

    priority_hashes = []
    other_hashes = []

    for c_url in sorted(chunk_urls):
        if any(skip in c_url for skip in ["polyfills-", "framework-"]):
            continue
        try:
            r = session.get(c_url, headers=BROWSER_HEADERS, verify=False, timeout=10)
            if r.status_code != 200:
                continue
            js = r.text

            for h in re.findall(r'createServerReference\)\("([0-9a-f]{40,44})"', js):
                if h not in priority_hashes:
                    priority_hashes.append(h)
            for h in re.findall(r'createServerReference\("([0-9a-f]{40,44})"', js):
                if h not in priority_hashes:
                    priority_hashes.append(h)

            if "tradingStatus" in js or "hasToken" in js or "todays-trade" in js or "menuData" in js:
                for h in re.findall(r'"([0-9a-f]{40,44})"', js):
                    if h not in priority_hashes:
                        priority_hashes.append(h)
            else:
                for h in re.findall(r'"([0-9a-f]{40,44})"', js):
                    if h not in other_hashes and h not in priority_hashes:
                        other_hashes.append(h)
        except Exception:
            continue

    return priority_hashes + other_hashes

def resolve_mse_session():
    """Сесс үүсгэж, mseSessionToken авч, Next-Action хэшийг шалгаж баталгаажуулах"""
    for attempt in range(1, 4):
        session = requests.Session()
        session.cookies.update(INITIAL_COOKIES)
        refresh_mse_session_token(session)

        try:
            _, parsed = call_mse_endpoint(session, "tradingStatus1Count", DEFAULT_NEXT_ACTION)
            if isinstance(parsed, dict):
                print(f"✅ Үндсэн Next-Action амжилттай холбогдлоо (Оролдлого {attempt}): {DEFAULT_NEXT_ACTION}")
                return session, DEFAULT_NEXT_ACTION
        except Exception as e:
            print(f"⚠️ Оролдлого {attempt} ({DEFAULT_NEXT_ACTION[:12]}...): {e}")

    # Хэрэв үндсэн хэш 404 өгвөл автоматаар шинэ хэш хайх
    session = requests.Session()
    session.cookies.update(INITIAL_COOKIES)
    refresh_mse_session_token(session)

    candidates = discover_candidate_actions(session)
    for h in candidates:
        if h == DEFAULT_NEXT_ACTION:
            continue
        try:
            _, parsed = call_mse_endpoint(session, "tradingStatus1Count", h)
            if isinstance(parsed, dict):
                print(f"✅ Шинэ Next-Action автоматаар олдлоо: {h}")
                return session, h
        except Exception:
            continue

    return session, DEFAULT_NEXT_ACTION

# ==========================================
# 5. COMEX (УУЛ УУРХАЙН БИРЖ) ТАТАХ ХЭСЭГ
# ==========================================

def parse_comex_table(url, date_str):
    try:
        r = requests.get(url, headers=BROWSER_HEADERS, timeout=20, verify=False)
        dfs = pd.read_html(io.StringIO(r.text), header=None)
        if not dfs:
            return None
        df = dfs[0].dropna(how="all")

        trades = []
        total_tons = 0
        total_usd = 0
        total_cny = 0

        for col in range(1, len(df.columns)):
            info = {}
            for _, row in df.iterrows():
                key = str(row[0]).lower()
                val = str(row[col])
                if val == "nan" or val == "None":
                    continue

                if "худалдагч" in key and "нэр" in key:
                    info["company"] = val
                elif "ангилал" in key:
                    info["type"] = val.split("/")[0].strip()
                elif "хэлцэл хийгдсэн үнэ" in key:
                    info["price"] = val
                elif "өсөлтийн хувь" in key:
                    info["growth"] = val
                elif "нийт үнийн дүн" in key:
                    info["total"] = val
                    amt_m = re.search(r"([\d,\.]+)\s*(USD|CNY|MNT)", val, re.IGNORECASE)
                    if amt_m:
                        amt = float(amt_m.group(1).replace(",", ""))
                        cur = amt_m.group(2).upper()
                        if cur == "USD":
                            total_usd += amt
                        if cur == "CNY":
                            total_cny += amt
                elif "хэмжээ" in key and "тонн" in key:
                    ton_m = re.search(r"(\d+)\s*тонн", val, re.IGNORECASE)
                    if ton_m:
                        tons = float(ton_m.group(1))
                        info["tons"] = tons
                        total_tons += tons

            if "company" in info:
                trades.append(info)

        text = f"📊 *COMEX — {date_str} УУЛ УУРХАЙН АРИЛЖААНЫ ТОЙМ*\n\n"
        text += f"📦 *Нийт борлуулалт:* {total_tons:,.0f} тонн\n"

        val_strs = []
        if total_usd > 0:
            val_strs.append(f"${total_usd / 1e6:,.1f} сая")
        if total_cny > 0:
            val_strs.append(f"{total_cny / 1e6:,.1f} сая CNY")
        if val_strs:
            text += f"💰 *Үнийн дүн:* {' | '.join(val_strs)}\n"
        text += "\n" + "—" * 20 + "\n\n"

        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        for i, t in enumerate(trades):
            emoji = emojis[i] if i < len(emojis) else "🔹"
            comp = t.get("company", "Тодорхойгүй")
            typ = t.get("type", "Бүтээгдэхүүн")
            qty = t.get("tons", 0)
            price = t.get("price", "-")
            growth = str(t.get("growth", "0%"))

            if "0%" in growth or growth == "0":
                growth_str = "➖ Өөрчлөлтгүй"
            elif "-" in growth:
                growth_str = f"▼ {growth} буурсан"
            else:
                growth_str = f"▲ +{growth.replace('+', '')} өссөн"

            item_total = t.get("total", "-")
            amt_m = re.search(r"([\d,\.]+)\s*(USD|CNY|MNT)", item_total, re.IGNORECASE)
            if amt_m:
                amt = float(amt_m.group(1).replace(",", ""))
                cur = amt_m.group(2).upper()
                if cur == "USD":
                    item_total = f"${amt / 1e6:,.1f} сая"
                elif cur == "CNY":
                    item_total = f"{amt / 1e6:,.1f} сая CNY"

            text += f"{emoji} *{comp}* | _{typ}_\n"
            text += f"▪️ *Хэмжээ:* {qty:,.0f} тонн\n"
            text += f"▪️ *Хаалтын ханш:* {price} ({growth_str})\n"
            text += f"▪️ *Нийт дүн:* {item_total}\n\n"

        text += f"🔗 [Дэлгэрэнгүй унших]({url})"
        return text
    except Exception as e:
        print(f"COMEX Хүснэгт задлахад алдаа: {e}")
        return None

def fetch_comex_news():
    print("\n🔎 COMEX (Уул уурхайн бирж) шалгаж байна...")
    url = f"{COMEX_BASE_URL}/show_trading_infos"
    today = datetime.now(ZoneInfo("Asia/Ulaanbaatar"))
    target_date_str = f"{today.month:02d}-р сарын {today.day:02d} өдрийн"

    try:
        r = requests.get(url, headers=BROWSER_HEADERS, timeout=20, verify=False)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "html.parser")

        for a in soup.find_all("a", href=True):
            title = re.sub(r"\s+", " ", a.get_text()).strip()
            title_lower = title.lower()
            if title_lower == "арилжааны мэдээлэл" or len(title) < 20:
                continue

            if "уул уурхайн бүтээгдэхүүний арилжааны мэдээ" in title_lower and target_date_str.lower() in title_lower:
                link = urljoin(COMEX_BASE_URL, a["href"])
                date_formatted = today.strftime("%Y.%m.%d")

                print("   ✅ COMEX мэдээ олдлоо. Хүснэгт татаж байна...")
                parsed_text = parse_comex_table(link, date_formatted)

                if parsed_text:
                    return parsed_text
                return f"📊 *COMEX (Уул уурхай)*\n\n{title}\n\n🔗 [Дэлгэрэнгүй унших]({link})"
    except Exception as e:
        print(f"❌ COMEX алдаа: {e}")
    return None

# ==========================================
# 6. МХБ ДАТА ТАТАХ & БАТАЛГААЖУУЛАХ
# ==========================================

def fetch_mse_data():
    print("=" * 70)
    print("МХБ ӨДРИЙН АРИЛЖААНЫ DATA ТАТАЛТ")
    print("=" * 70)

    session, active_action = resolve_mse_session()

    # Сүүлийн шинэчлэгдсэн цагийг шалгах (updateTime endpoint)
    try:
        _, upd_parsed = call_mse_endpoint(session, "updateTime", active_action, parameter="")
        if upd_parsed:
            print(f"🕒 МХБ сервер дээрх updateTime: {upd_parsed}")
    except Exception:
        pass

    all_records = []
    validation = []

    print("\n📊 ҮНДСЭН DATA ENDPOINT-ҮҮД\n")

    for order, (endpoint, category, currency) in enumerate(DATA_ENDPOINTS, 1):
        print(f"[{order:02d}/{len(DATA_ENDPOINTS)}] {category:<45} {endpoint}")
        try:
            response, parsed = call_mse_endpoint(session, endpoint, active_action)
            if not isinstance(parsed, list):
                print(f"   ⚠️ LIST биш: {type(parsed).__name__}")
                validation.append({
                    "endpoint": endpoint, "category": category,
                    "expected": None, "actual": 0, "status": "EMPTY/NOT_LIST"
                })
                continue

            actual_count = len(parsed)
            print(f"   HTTP={response.status_code} SIZE={len(response.content):,} ROWS={actual_count}")

            validation.append({
                "endpoint": endpoint, "category": category,
                "expected": None, "actual": actual_count, "status": "OK"
            })

            for obj in parsed:
                if not isinstance(obj, dict):
                    continue
                ticker = obj.get("companySymbol") or obj.get("bondSymbol")
                if not ticker:
                    continue

                turnover = to_number(obj.get("Turnover"))
                volume = to_number(obj.get("Volume"))
                change_pct = to_number(obj.get("changePercentage"))
                previous_close = to_number(obj.get("PreviousClose"))
                closing_price = to_number(obj.get("ClosingPrice"))

                if change_pct == 0 and previous_close > 0 and closing_price > 0:
                    change_pct = round(((closing_price - previous_close) / previous_close) * 100, 2)

                all_records.append({
                    "Дараалал": order,
                    "Endpoint": endpoint,
                    "Ангилал": category,
                    "Валют": currency,
                    "Тикер": ticker,
                    "Код": obj.get("code"),
                    "Нээлт": to_number(obj.get("OpeningPrice")),
                    "Дээд": to_number(obj.get("HighPrice")),
                    "Доод": to_number(obj.get("LowPrice")),
                    "Сүүлийн ханш": to_number(obj.get("LastTradedPrice")),
                    "Өмнөх хаалт": previous_close,
                    "Хаалтын ханш": closing_price,
                    "Өөрчлөлт": to_number(obj.get("Changes")),
                    "Өөрчлөлт %": change_pct,
                    "Ширхэг": volume,
                    "Дүн": turnover,
                    "Авах тоо": to_number(obj.get("BuyOrderQty")),
                    "Авах үнэ": to_number(obj.get("HighestBidPrice")),
                    "Зарах тоо": to_number(obj.get("SellOrderQty")),
                    "Зарах үнэ": to_number(obj.get("LowestOfferPrice")),
                })
        except Exception as e:
            print(f"   ❌ АЛДАА: {e}")
            validation.append({
                "endpoint": endpoint, "category": category,
                "expected": None, "actual": 0, "status": f"ERROR: {e}"
            })

    df = pd.DataFrame(all_records)

    print("\n" + "=" * 70)
    print("COUNT ENDPOINT-ҮҮДИЙН ШАЛГАЛТ")
    print("=" * 70)

    count_data = {}
    for count_endpoint, category in COUNT_ENDPOINTS:
        print(f"\n{count_endpoint:<28} {category}")
        try:
            response, parsed = call_mse_endpoint(session, count_endpoint, active_action)
            if not isinstance(parsed, dict):
                print("   ⚠️ COUNT response object биш")
                continue

            company_count = int(to_number(parsed.get("company_count")))
            volume = to_number(parsed.get("volume"))
            turnover = to_number(parsed.get("turnover"))

            count_data[count_endpoint] = {
                "category": category, "company_count": company_count,
                "volume": volume, "turnover": turnover,
            }

            print(f"   Company: {company_count:,} | Volume: {volume:,.0f} | Turnover: {turnover:,.2f}")

            data_endpoint = count_endpoint.replace("Count", "")
            if not df.empty:
                subset = df[df["Endpoint"] == data_endpoint]
                actual_company_count = len(subset)
                actual_volume = subset["Ширхэг"].sum()
                actual_turnover = subset["Дүн"].sum()
            else:
                actual_company_count, actual_volume, actual_turnover = 0, 0, 0

            company_ok = (actual_company_count == company_count)
            volume_ok = (abs(actual_volume - volume) < 0.01)
            turnover_ok = (abs(actual_turnover - turnover) < 0.01)

            print("   Company check : " + ("✅" if company_ok else "❌"))
            print("   Volume check  : " + ("✅" if volume_ok else "❌"))
            print("   Turnover check: " + ("✅" if turnover_ok else "❌"))

            for item in validation:
                if item["endpoint"] == data_endpoint:
                    item["expected"] = company_count
                    item["count_check"] = "OK" if (company_ok and volume_ok and turnover_ok) else "MISMATCH"
                    item["count_volume"] = volume
                    item["actual_volume"] = actual_volume
                    item["count_turnover"] = turnover
                    item["actual_turnover"] = actual_turnover
                    break
        except Exception as e:
            print(f"   ❌ COUNT ERROR: {e}")

    mn_now = datetime.now(ZoneInfo("Asia/Ulaanbaatar"))
    trade_date = f"{mn_now.year} ОНЫ {mn_now.month} ДҮГЭЭР САРЫН {mn_now.day}-НЫ ӨДРИЙН"
    validation_df = pd.DataFrame(validation)
    return df, trade_date, count_data, validation_df

# ==========================================
# 7. TEXT SUMMARY (БҮХ БҮЛГИЙГ БАГТААСАН ЗАГВАР)
# ==========================================

def generate_summary_text(df, trade_date, count_data):
    if df.empty:
        return f"📊 *МХБ — {trade_date} АРИЛЖААНЫ ТОЙМ*\n\n⚠️ Арилжааны дата олдсонгүй."

    mnt_df = df[df["Валют"] == "MNT"]
    usd_df = df[df["Валют"] == "USD"]

    stocks_and_funds = df[
        df["Ангилал"].isin([
            "Хувьцаат компанийн I ангилал",
            "Хувьцаат компанийн II ангилал",
            "Хувьцаат компанийн III ангилал",
            "Хөрөнгө оруулалтын сан",
        ])
    ].copy()

    text = f"📊 *МХБ — {trade_date} АРИЛЖААНЫ ТОЙМ*\n\n"
    text += f"💰 Нийт MNT арилжаа: {mnt_df['Дүн'].sum():,.0f} ₮\n"
    if not usd_df.empty and usd_df["Дүн"].sum() > 0:
        text += f"💵 Нийт USD арилжаа: {usd_df['Дүн'].sum():,.2f} USD\n"
    text += "\n"

    stock_qty = stocks_and_funds["Ширхэг"].sum()
    stock_turnover = stocks_and_funds["Дүн"].sum()

    text += f"📈 Хувьцаа + сангийн арилжаа: {stock_turnover:,.0f} ₮\n"
    text += f"📦 Арилжаалсан хэмжээ: {stock_qty:,.0f} ширхэг\n\n"

    top10 = stocks_and_funds.sort_values("Дүн", ascending=False).head(10)
    if not top10.empty and top10["Дүн"].sum() > 0:
        text += "🏆 *Хамгийн их үнийн дүнтэй TOP 10:*\n"
        for i, (_, row) in enumerate(top10.iterrows(), 1):
            text += f"{i}. {row['Тикер']} — {row['Дүн']:,.0f} ₮\n"
        text += "\n"

    gainers = stocks_and_funds[stocks_and_funds["Өөрчлөлт %"] > 0].sort_values("Өөрчлөлт %", ascending=False).head(3)
    if not gainers.empty:
        text += "📈 *Хамгийн их өсөлттэй:*\n"
        for _, row in gainers.iterrows():
            text += f"🟩 {row['Тикер']} +{row['Өөрчлөлт %']:.2f}%\n"
        text += "\n"

    losers = stocks_and_funds[stocks_and_funds["Өөрчлөлт %"] < 0].sort_values("Өөрчлөлт %", ascending=True).head(3)
    if not losers.empty:
        text += "📉 *Хамгийн их бууралттай:*\n"
        for _, row in losers.iterrows():
            text += f"🟥 {row['Тикер']} {row['Өөрчлөлт %']:.2f}%\n"
        text += "\n"

    funds_df = df[df["Ангилал"] == "Хөрөнгө оруулалтын сан"]
    if not funds_df.empty and funds_df["Дүн"].sum() > 0:
        text += "🏦 *Хөрөнгө оруулалтын сан:*\n"
        text += f"▪️ Сангийн тоо: {len(funds_df[funds_df['Дүн'] > 0])}\n"
        text += f"▪️ Арилжаалсан нэгж эрх: {funds_df['Ширхэг'].sum():,.0f}\n"
        text += f"▪️ Нийт үнийн дүн: {funds_df['Дүн'].sum():,.0f} ₮\n\n"

    bonds_df = df[df["Ангилал"] == "Компанийн бондын хоёрдогч зах зээлийн арилжаа"]
    if not bonds_df.empty and bonds_df["Дүн"].sum() > 0:
        text += "📄 *Компанийн бонд:*\n"
        text += f"▪️ Бондын төрөл тоо: {len(bonds_df[bonds_df['Дүн'] > 0])}\n"
        text += f"▪️ Тоо ширхэг: {bonds_df['Ширхэг'].sum():,.0f}\n"
        text += f"▪️ Нийт үнийн дүн: {bonds_df['Дүн'].sum():,.0f} ₮\n\n"

    usd_bonds = df[df["Ангилал"] == "Компанийн бондын хоёрдогч зах зээл USD"]
    if not usd_bonds.empty and usd_bonds["Дүн"].sum() > 0:
        text += "💵 *Компанийн бонд (USD):*\n"
        text += f"▪️ Тоо ширхэг: {usd_bonds['Ширхэг'].sum():,.0f}\n"
        text += f"▪️ Нийт үнийн дүн: ${usd_bonds['Дүн'].sum():,.2f}\n\n"

    abs_df = df[df["Ангилал"] == "Хөрөнгөөр баталгаажсан үнэт цаас"]
    if not abs_df.empty and abs_df["Дүн"].sum() > 0:
        text += "📜 *Хөрөнгөөр баталгаажсан үнэт цаас (ХБҮЦ):*\n"
        text += f"▪️ Тоо ширхэг: {abs_df['Ширхэг'].sum():,.0f}\n"
        text += f"▪️ Нийт үнийн дүн: {abs_df['Дүн'].sum():,.0f} ₮\n\n"

    zg_df = df[df["Ангилал"] == "ЗГҮЦ хоёрдогч зах зээлийн арилжаа"]
    if not zg_df.empty and zg_df["Дүн"].sum() > 0:
        text += "🏛️ *Засгийн газрын үнэт цаас (ЗГҮЦ):*\n"
        text += f"▪️ Ширхэг: {zg_df['Ширхэг'].sum():,.0f}\n"
        text += f"▪️ Нийт үнийн дүн: {zg_df['Дүн'].sum():,.0f} ₮\n\n"

    block_df = df[df["Ангилал"] == "Багцын арилжаа"]
    if not block_df.empty and block_df["Дүн"].sum() > 0:
        text += "📦 *Багцын арилжаа:*\n"
        text += f"▪️ Ширхэг: {block_df['Ширхэг'].sum():,.0f}\n"
        text += f"▪️ Нийт үнийн дүн: {block_df['Дүн'].sum():,.0f} ₮\n\n"

    block_usd_df = df[df["Ангилал"] == "Багцын арилжаа USD"]
    if not block_usd_df.empty and block_usd_df["Дүн"].sum() > 0:
        text += "📦 *Багцын арилжаа (USD):*\n"
        text += f"▪️ Ширхэг: {block_usd_df['Ширхэг'].sum():,.0f}\n"
        text += f"▪️ Нийт үнийн дүн: ${block_usd_df['Дүн'].sum():,.2f}\n\n"

    aon_df = df[df["Ангилал"] == "AON арилжаа"]
    if not aon_df.empty and aon_df["Дүн"].sum() > 0:
        text += "🤝 *AON арилжаа:*\n"
        text += f"▪️ Ширхэг: {aon_df['Ширхэг'].sum():,.0f}\n"
        text += f"▪️ Нийт үнийн дүн: {aon_df['Дүн'].sum():,.0f} ₮\n\n"

    return text

# ==========================================
# 8. HEATMAP ЗУРАГ БЭЛТГЭХ
# ==========================================

def create_heatmap(df, title):
    heatmap_df = df[
        df["Ангилал"].isin([
            "Хувьцаат компанийн I ангилал",
            "Хувьцаат компанийн II ангилал",
            "Хувьцаат компанийн III ангилал",
        ])
    ].copy()

    heatmap_df = heatmap_df[heatmap_df["Дүн"] > 0]
    if heatmap_df.empty:
        return None

    heatmap_df = heatmap_df.sort_values("Дүн", ascending=False)
    fig, ax = plt.subplots(figsize=(12, 9))
    sizes = heatmap_df["Дүн"].values
    normed = squarify.normalize_sizes(sizes, 100, 100)
    rects = squarify.squarify(normed, 0, 0, 100, 100)

    colors = []
    for change in heatmap_df["Өөрчлөлт %"]:
        if change > 0:
            colors.append("#2ca02c")
        elif change < 0:
            colors.append("#d62728")
        else:
            colors.append("#7f7f7f")

    for i, (rect, (_, row)) in enumerate(zip(rects, heatmap_df.iterrows())):
        ax.add_patch(
            plt.Rectangle(
                (rect["x"], rect["y"]), rect["dx"], rect["dy"],
                facecolor=colors[i], edgecolor="white", linewidth=2, alpha=0.9
            )
        )
        ratio = (rect["dx"] * rect["dy"]) / 10000
        font_size = max(7, min(24, int(7 + (28 - 7) * np.sqrt(ratio))))
        change = row["Өөрчлөлт %"]
        sign = "+" if change > 0 else ""
        if ratio < 0.02:
            label = row["Тикер"]
        else:
            label = f"{row['Тикер']}\n{sign}{change:.2f}%\n{row['Дүн']:,.0f} ₮"

        ax.text(
            rect["x"] + rect["dx"] / 2, rect["y"] + rect["dy"] / 2,
            label, ha="center", va="center", fontsize=font_size, color="white", fontweight="bold"
        )

    fig.text(0.5, 0.5, "Ganbayar Batsuuri", fontsize=40, color="grey", ha="center", va="center", alpha=0.15, rotation=30)
    plt.title(title, fontsize=16, fontweight="bold", pad=20)
    plt.xlim(0, 100)
    plt.ylim(0, 100)
    plt.axis("off")
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close()
    buf.seek(0)
    return buf

# ==========================================
# 9. TELEGRAM ИЛГЭЭХ ФУНКЦҮҮД
# ==========================================

def send_telegram_photo(photo_buf, caption=""):
    if not BOT_TOKEN:
        print("⚠️ BOT_TOKEN тохируулагдаагүй.")
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    try:
        response = requests.post(
            url,
            files={"photo": ("chart.png", photo_buf, "image/png")},
            data={"chat_id": CHANNEL, "caption": caption},
            timeout=30
        )
        print("Telegram photo status:", response.status_code)
        return response.ok
    except Exception as e:
        print("❌ Telegram photo error:", e)
        return False

def send_telegram_message(text):
    if not BOT_TOKEN:
        print("⚠️ BOT_TOKEN тохируулагдаагүй.")
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        response = requests.post(
            url,
            data={
                "chat_id": CHANNEL,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            },
            timeout=30
        )
        print("Telegram message status:", response.status_code)
        if not response.ok:
            print("Telegram error text:", response.text[:1000])
        return response.ok
    except Exception as e:
        print("❌ Telegram message error:", e)
        return False

# ==========================================
# 10. VALIDATION ХЭВЛЭХ & CSV ХАДГАЛАХ
# ==========================================

def print_validation(validation_df):
    print("\n" + "=" * 90 + "\nMSE DATA VALIDATION\n" + "=" * 90)
    if validation_df.empty:
        print("Validation data байхгүй.")
        return
    for _, row in validation_df.iterrows():
        endpoint = row["endpoint"]
        expected = row.get("expected", None)
        actual = row.get("actual", 0)
        check = row.get("count_check", "-")
        print(f"{endpoint:<28} ROWS={actual:<4} COUNT={expected!s:<4} {check}")

def save_local_data(df, validation_df):
    timestamp = datetime.now(ZoneInfo("Asia/Ulaanbaatar")).strftime("%Y%m%d_%H%M%S")
    csv_file = f"mse_today_{timestamp}.csv"
    validation_file = f"mse_validation_{timestamp}.csv"

    df.to_csv(csv_file, index=False, encoding="utf-8-sig")
    validation_df.to_csv(validation_file, index=False, encoding="utf-8-sig")
    print(f"\n💾 Data CSV: {csv_file}\n💾 Validation CSV: {validation_file}")
    return csv_file, validation_file

# ==========================================
# 11. MAIN
# ==========================================

def main():
    print("\n🚀 МХБ & COMEX ӨДРИЙН АРИЛЖААНЫ БОТ ЭХЭЛЛЭЭ...\n")

    # 1. Үндсэн МХБ дата татах
    df, trade_date, count_data, validation_df = fetch_mse_data()
    print_validation(validation_df)

    if df.empty:
        print("\n❌ МХБ өгөгдөл олдсонгүй.")
        send_telegram_message("⚠️ МХБ-ийн өнөөдрийн арилжааны дата олдсонгүй.")
    else:
        save_local_data(df, validation_df)
        summary_text = generate_summary_text(df, trade_date, count_data)
        print("\n" + "=" * 70 + "\nTELEGRAM SUMMARY\n" + "=" * 70)
        print(summary_text)

        send_telegram_message(summary_text)

        heatmap_buf = create_heatmap(df, f"МХБ НЭГДСЭН ЗУРАГ ({trade_date})")
        if heatmap_buf:
            send_telegram_photo(heatmap_buf, "📊 МХБ-ийн хувьцааны арилжааны хөдөлгөөн")

    # 2. COMEX Уул уурхайн биржийн мэдээг шалгаж явуулах
    comex_text = fetch_comex_news()
    if comex_text:
        print("   ✅ COMEX мэдээ Телеграм руу илгээгдэж байна...")
        send_telegram_message(comex_text)
    else:
        print("   ℹ️ Өнөөдрийн COMEX мэдээ одоогоор гараагүй эсвэл олдсонгүй.")

    print("\n" + "=" * 70 + "\n✅ АЖИЛЛАЖ ДУУСЛАА\n" + "=" * 70)

if __name__ == "__main__":
    main()

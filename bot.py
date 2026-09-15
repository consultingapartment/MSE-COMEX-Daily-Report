# ==========================================
# МХБ ӨДРИЙН АРИЛЖААНЫ ТОЙМ - TELEGRAM BOT (БҮРЭН ЭХЭЛРЭХ КОД)
# ==========================================

import os
import requests
import json
import re
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import squarify
import io
import urllib3
from datetime import datetime
from zoneinfo import ZoneInfo

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# 1. ТОХИРГОО
# ==========================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL = os.getenv("CHANNEL", "@openburry")

plt.rcParams["font.family"] = "DejaVu Sans"

MSE_URL = "https://mse.mn/todays-trade"

NEXT_ACTION = "6d867ebd99fb6edef2f9537b22668cd0c00a71c2"

NEXT_ROUTER_STATE_TREE = (
    '%5B%22%22%2C%7B%22children%22%3A%5B'
    '%22%28navbar%29%22%2C%7B%22children%22%3A%5B'
    '%22%28trade%29%22%2C%7B%22children%22%3A%5B'
    '%22todays-trade%22%2C%7B%22children%22%3A%5B'
    '%22__PAGE__%22%2C%7B%7D%2C%22%2Ftodays-trade%22%2C%22refresh%22'
    '%5D%7D%5D%7D%5D%7D%5D%7D%2Cnull%2Cnull%2Ctrue%5D'
)

HEADERS = {
    "Accept": "text/x-component",
    "Accept-Language": "en-US,en;q=0.9,mn;q=0.8",
    "Content-Type": "text/plain;charset=UTF-8",
    "DNT": "1",
    "Next-Action": NEXT_ACTION,
    "Next-Router-State-Tree": NEXT_ROUTER_STATE_TREE,
    "Origin": "https://mse.mn",
    "Referer": "https://mse.mn/todays-trade",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/153.0.0.0 Safari/537.36"
    ),
    "sec-ch-ua": (
        '"Google Chrome";v="153", '
        '"Not_A Brand";v="8", '
        '"Chromium";v="153"'
    ),
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}

COOKIES = {
    "_ga": "GA1.1.880138786.1757978109",
    "twk_uuid_63cf736547425128790f4ccf": (
        "%7B%22uuid%22%3A%22"
        "1.MSPsb2oEazmyvFvbtbNskGiR8804FNrb0jHm1K9kkWOvva2uryRbfbvf8HSoKUAnD7QxdZGcRaWLlXmdlekf1mb1ISNsBnoAT9WNjuWfMmLGI"
        "%22%2C%22version%22%3A3%2C%22domain%22%3A%22mse.mn%22"
        "%2C%22ts%22%3A1788942482023%7D"
    ),
    "_ga_4JVXGPBK2L": (
        "GS2.1.s1789177239$o399$g1$t1789177252$j47$l0$h0"
    ),
}

# ==========================================
# 2. MSE DATA ENDPOINT-ҮҮД
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

# ==========================================
# 3. COUNT ENDPOINT-ҮҮД
# ==========================================

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
# 4. ТООН УТГА ЦЭВЭРЛЭХ
# ==========================================

def to_number(value):
    if value is None:
        return 0.0
    if isinstance(value, (int, float, np.number)):
        return float(value)
    text = str(value).strip()
    if not text:
        return 0.0
    text = (
        text
        .replace(",", "")
        .replace(" ", "")
        .replace("₮", "")
        .replace("$", "")
    )
    try:
        return float(text)
    except Exception:
        return 0.0

# ==========================================
# 5. RSC RESPONSE PARSER
# ==========================================

def parse_rsc_response(response_text):
    lines = response_text.splitlines()
    for line in lines:
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

# ==========================================
# 6. НЭГ SERVER ACTION ДУУДАХ
# ==========================================

def call_mse_endpoint(session, endpoint):
    payload = json.dumps([
        {
            "url": endpoint,
            "parameter": "?lang=mn",
            "config": {
                "hasToken": False
            }
        }
    ])
    response = session.post(
        MSE_URL,
        headers=HEADERS,
        cookies=COOKIES,
        data=payload,
        timeout=30
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"HTTP {response.status_code}: {response.text[:500]}"
        )
    parsed = parse_rsc_response(response.text)
    return response, parsed

# ==========================================
# 7. БҮХ DATA + COUNT ТАТАХ
# ==========================================

def fetch_mse_data():
    print("=" * 70)
    print("МХБ ӨДРИЙН АРИЛЖААНЫ DATA ТАТАЛТ")
    print("=" * 70)

    session = requests.Session()
    all_records = []
    validation = []

    print("\n📊 ҮНДСЭН DATA ENDPOINT-ҮҮД\n")

    for order, (endpoint, category, currency) in enumerate(DATA_ENDPOINTS, 1):
        print(f"[{order:02d}/{len(DATA_ENDPOINTS)}] {category:<45} {endpoint}")
        try:
            response, parsed = call_mse_endpoint(session, endpoint)
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
            response, parsed = call_mse_endpoint(session, count_endpoint)
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

            print(f"   Company: {company_count:,}")
            print(f"   Volume : {volume:,.0f}")
            print(f"   Turnover: {turnover:,.2f}")

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
                    item["count_check"] = "OK" if company_ok else "MISMATCH"
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
# 8. TEXT SUMMARY (БҮХ БҮЛГИЙГ БҮРЭН БАГБААСАН ЗАГВАР)
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
    if not usd_df.empty and usd_df['Дүн'].sum() > 0:
        text += f"💵 Нийт USD арилжаа: {usd_df['Дүн'].sum():,.2f} USD\n"
    text += "\n"

    stock_qty = stocks_and_funds["Ширхэг"].sum()
    stock_turnover = stocks_and_funds["Дүн"].sum()

    text += f"📈 Хувьцаа + сангийн арилжаа: {stock_turnover:,.0f} ₮\n"
    text += f"📦 Арилжаалсан хэмжээ: {stock_qty:,.0f} ширхэг\n\n"

    top10 = stocks_and_funds.sort_values("Дүн", ascending=False).head(10)
    if not top10.empty and top10['Дүн'].sum() > 0:
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
# 9. HEATMAP ЗУРАГ БЭЛТГЭХ
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

    fig.text(0.5, 0.5, 'Ganbayar Batsuuri', fontsize=40, color='grey', ha='center', va='center', alpha=0.15, rotation=30)
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
# 10. TELEGRAM PHOTO
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
        print("Telegram photo:", response.status_code)
        return response.ok
    except Exception as e:
        print("❌ Telegram photo error:", e)
        return False

# ==========================================
# 11. TELEGRAM MESSAGE
# ==========================================

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
        print("Telegram message:", response.status_code)
        if not response.ok:
            print(response.text[:1000])
        return response.ok
    except Exception as e:
        print("❌ Telegram message error:", e)
        return False

# ==========================================
# 12. VALIDATION ХЭВЛЭХ
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

# ==========================================
# 13. CSV-Д ХАДГАЛАХ
# ==========================================

def save_local_data(df, validation_df, trade_date):
    timestamp = datetime.now(ZoneInfo("Asia/Ulaanbaatar")).strftime("%Y%m%d_%H%M%S")
    csv_file = f"mse_today_{timestamp}.csv"
    validation_file = f"mse_validation_{timestamp}.csv"
    
    df.to_csv(csv_file, index=False, encoding="utf-8-sig")
    validation_df.to_csv(validation_file, index=False, encoding="utf-8-sig")
    print(f"\n💾 Data CSV: {csv_file}\n💾 Validation CSV: {validation_file}")
    return csv_file, validation_file

# ==========================================
# 14. MAIN
# ==========================================

def main():
    print("\n🚀 МХБ ӨДРИЙН АРИЛЖААНЫ БОТ ЭХЭЛЛЭЭ...\n")

    df, trade_date, count_data, validation_df = fetch_mse_data()
    print_validation(validation_df)

    if df.empty:
        print("\n❌ МХБ өгөгдөл олдсонгүй.")
        send_telegram_message("⚠️ МХБ-ийн өнөөдрийн арилжааны дата олдсонгүй.")
        return

    print("\n" + "=" * 70 + "\nНЭГДСЭН DATA\n" + "=" * 70)
    print(f"Нийт мөр: {len(df):,}")
    print(f"Нийт MNT дүн: {df[df['Валют'] == 'MNT']['Дүн'].sum():,.2f} ₮")
    print(f"Нийт USD дүн: {df[df['Валют'] == 'USD']['Дүн'].sum():,.2f} USD")

    summary_text = generate_summary_text(df, trade_date, count_data)
    print("\n" + "=" * 70 + "\nTELEGRAM SUMMARY\n" + "=" * 70)
    print(summary_text)

    save_local_data(df, validation_df, trade_date)
    send_telegram_message(summary_text)

    heatmap_buf = create_heatmap(df, f"МХБ НЭГДСЭН ЗУРАГ ({trade_date})")
    if heatmap_buf:
        send_telegram_photo(heatmap_buf, "📊 МХБ-ийн хувьцааны арилжааны хөдөлгөөн")

    print("\n" + "=" * 70 + "\n✅ АЖИЛЛАЖ ДУУСЛАА\n" + "=" * 70)

if __name__ == "__main__":
    main()

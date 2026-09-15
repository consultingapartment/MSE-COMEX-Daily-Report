# ==========================================
# МХБ ӨДРИЙН АРИЛЖААНЫ ТОЙМ - TELEGRAM BOT (ЭЦСИЙН ХУВИЛБАР)
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

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# 1. ТОХИРГОО
# ==========================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL = os.getenv("CHANNEL", "@openburry")

plt.rcParams['font.family'] = 'DejaVu Sans'

# ==========================================
# 2. МХБ - БҮХ ENDPOINT-ҮҮДЭЭС ДАТА ТАТАХ
# ==========================================
def fetch_mse_data():
    print("🌐 МХБ Server Action-уудаас дата татаж байна...")
    url = "https://mse.mn/todays-trade"
    
    headers = {
        "Accept": "text/x-component",
        "Accept-Language": "en-US,en;q=0.9,mn;q=0.8",
        "Connection": "keep-alive",
        "Content-Type": "text/plain;charset=UTF-8",
        "DNT": "1",
        "Next-Action": "6d867ebd99fb6edef2f9537b22668cd0c00a71c2",
        "Next-Router-State-Tree": '%5B%22%22%2C%7B%22children%22%3A%5B%22%28navbar%29%22%2C%7B%22children%22%3A%5B%22%28trade%29%22%2C%7B%22children%22%3A%5B%22todays-trade%22%2C%7B%22children%22%3A%5B%22__PAGE__%22%2C%7B%7D%2C%22%2Ftodays-trade%22%2C%22refresh%22%5D%7D%5D%7D%5D%7D%5D%7D%2Cnull%2Cnull%2Ctrue%5D',
        "Origin": "https://mse.mn",
        "Referer": "https://mse.mn/todays-trade",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
        "sec-ch-ua": '"Google Chrome";v="153", "Not_A Brand";v="8", "Chromium";v="153"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    }
    
    cookies = {
        "_ga": "GA1.1.880138786.1757978109",
        "twk_uuid_63cf736547425128790f4ccf": "%7B%22uuid%22%3A%221.MSPsb2oEazmyvFvbtbNskGiR8804FNrb0jHm1K9kkWOvva2uryRbfbvf8HSoKUAnD7QxdZGcRaWLlXmdlekf1mb1ISNsBnoAT9WNjuWfMmLGI%22%2C%22version%22%3A3%2C%22domain%22%3A%22mse.mn%22%2C%22ts%22%3A1788942482023%7D",
        "_ga_4JVXGPBK2L": "GS2.1.s1789177239$o399$g1$t1789177252$j47$l0$h0",
    }

    endpoints = [
        ("tradingStatus1", "Хувьцаа I"),
        ("tradingStatus2", "Хувьцаа II"),
        ("tradingStatus3", "Хувьцаа III"),
        ("tradingXoc", "Хөрөнгө оруулалтын сан"),
        ("tradingAbs", "ХБҮЦ"),
        ("tradingStatusXK", "Компанийн бонд"),
        ("tradingStatusUSD", "Долларын бонд"),
        ("tradingBlock", "Багцын арилжаа"),
        ("tradingBlockUSD", "Багцын арилжаа (USD)")
    ]

    all_records = []

    for ep, category_name in endpoints:
        payload = json.dumps([{"url": ep, "parameter": "?lang=mn", "config": {"hasToken": False}}])
        try:
            response = requests.post(url, headers=headers, cookies=cookies, data=payload, verify=False, timeout=15)
            if response.status_code == 200:
                match = re.search(r'1:\s*(\[.*?\])', response.text)
                if match:
                    items = json.loads(match.group(1))
                    for obj in items:
                        ticker = obj.get("companySymbol") or obj.get("bondSymbol")
                        if not ticker: continue
                            
                        turnover = float(str(obj.get("Turnover", "0")).replace(",", "").replace(" ", "") or 0)
                        volume = float(str(obj.get("Volume", "0")).replace(",", "").replace(" ", "") or 0)
                        
                        # Өөрчлөлтийн хувь тооцоолох
                        prev = float(str(obj.get("PreviousClose", "0")).replace(",", "") or 0)
                        close = float(str(obj.get("ClosingPrice", "0")).replace(",", "") or 0)
                        change_pct = float(str(obj.get("changePercentage", "0")).replace(",", "") or 0)
                        if change_pct == 0 and prev > 0 and close > 0:
                            change_pct = round(((close - prev) / prev) * 100, 2)
                        
                        if turnover > 0:
                            all_records.append({
                                "Тикер": ticker,
                                "Дүн": turnover,
                                "Ширхэг": volume,
                                "Өөрчлөлт": change_pct,
                                "Ангилал": category_name
                            })
        except Exception as e:
            print(f"❌ [{ep}] алдаа: {e}")

    df = pd.DataFrame(all_records)
    if not df.empty:
        df = df.groupby(['Тикер', 'Өөрчлөлт', 'Ангилал'], as_index=False).agg({'Дүн': 'sum', 'Ширхэг': 'sum'})
        
    mn_time = datetime.utcnow() + pd.Timedelta(hours=8)
    trade_date = f"{mn_time.year} ОНЫ {mn_time.month} ДҮГЭЭР САРЫН {mn_time.day}-НЫ ӨДРИЙН"
    return df, trade_date

# ==========================================
# 3. ТЕКСТ ТОЙМ БЭЛТГЭХ (ХУУЧИН ЗАГВАРААР)
# ==========================================
def generate_summary_text(df, trade_date):
    if df.empty: return "📊 Өнөөдрийн арилжааны дата олдсонгүй."
        
    total_amount = df['Дүн'].sum()
    total_qty = df['Ширхэг'].sum()
    
    text = f"📊 *МХБ — {trade_date} АРИЛЖААНЫ ТОЙМ*\n\n"
    text += f"💰 Нийт арилжаа: {total_amount:,.0f} ₮\n"
    text += f"📦 Нийт хувьцаа: {total_qty:,.0f} ширхэг\n\n"
    
    # 🏆 TOP 10 (Зөвхөн Хувьцаа болон Сангууд орох ёстой, бонд/хбүц орохгүй)
    stocks_and_funds = df[df['Ангилал'].isin(['Хувьцаа I', 'Хувьцаа II', 'Хувьцаа III', 'Хөрөнгө оруулалтын сан'])]
    top10 = stocks_and_funds.sort_values('Дүн', ascending=False).head(10)
    
    text += "🏆 *Хамгийн их үнийн дүнтэй TOP 10:*\n"
    for i, (_, r) in enumerate(top10.iterrows(), 1): 
        text += f"{i}. {r['Тикер']} — {r['Дүн']:,.0f} ₮\n"
            
    # 📈 Хамгийн өсөлттэй TOP 3
    gainers = stocks_and_funds[stocks_and_funds['Өөрчлөлт'] > 0].sort_values('Өөрчлөлт', ascending=False).head(3)
    if not gainers.empty:
        text += "\n📈 *Хамгийн их өсөлттэй:*\n"
        for _, r in gainers.iterrows(): 
            text += f"🟩 {r['Тикер']} +{r['Өөрчлөлт']}%\n"
            
    # 📉 Хамгийн бууралттай TOP 3
    losers = stocks_and_funds[stocks_and_funds['Өөрчлөлт'] < 0].sort_values('Өөрчлөлт', ascending=True).head(3)
    if not losers.empty:
        text += "\n📉 *Хамгийн их бууралттай:*\n"
        for _, r in losers.iterrows(): 
            text += f"🟥 {r['Тикер']} {r['Өөрчлөлт']}%\n"

    # 🏢 Хөрөнгө оруулалтын сангийн тойм
    funds_df = df[df['Ангилал'] == 'Хөрөнгө оруулалтын сан']
    if not funds_df.empty:
        text += f"\n🏦 *Хөрөнгө оруулалтын сан:*\n"
        text += f"▪️ Сангийн тоо: {len(funds_df)}\n"
        text += f"▪️ Арилжаалсан нэгж эрх: {funds_df['Ширхэг'].sum():,.0f}\n"
        text += f"▪️ Нийт үнийн дүн: {funds_df['Дүн'].sum():,.0f} ₮\n"

    # 📄 Бонд болон бусад бүтээгдэхүүний мэдээлэл (Шинээр нэмэгдсэн хэсэг)
    bonds_df = df[df['Ангилал'].isin(['Компанийн бонд', 'Долларын бонд'])]
    if not bonds_df.empty:
        text += f"\n📄 *Компанийн бонд:*\n"
        text += f"▪️ Нийт үнийн дүн: {bonds_df['Дүн'].sum():,.0f} ₮\n"
        text += f"▪️ Тоо ширхэг: {bonds_df['Ширхэг'].sum():,.0f}\n"

    abs_df = df[df['Ангилал'] == 'ХБҮЦ']
    if not abs_df.empty:
        text += f"\n📜 *Хөрөнгөөр баталгаажсан үнэт цаас (ХБҮЦ):*\n"
        text += f"▪️ Нийт үнийн дүн: {abs_df['Дүн'].sum():,.0f} ₮\n"

    block_df = df[df['Ангилал'].isin(['Багцын арилжаа', 'Багцын арилжаа (USD)'])]
    if not block_df.empty:
        text += f"\n📦 *Багцын арилжаа:*\n"
        text += f"▪️ Нийт үнийн дүн: {block_df['Дүн'].sum():,.0f} ₮\n"
            
    return text

# ==========================================
# 4. HEATMAP ЗУРАГ БЭЛТГЭХ
# ==========================================
def create_heatmap(df, title):
    heatmap_df = df[df['Ангилал'].isin(['Хувьцаа I', 'Хувьцаа II', 'Хувьцаа III'])].copy()
    if heatmap_df.empty: return None

    fig, ax = plt.subplots(figsize=(12, 9))
    colors = ['#2ca02c' if c > 0 else '#d62728' if c < 0 else '#7f7f7f' for c in heatmap_df['Өөрчлөлт']]
    normed = squarify.normalize_sizes(heatmap_df['Дүн'].values, 100, 100)
    rects = squarify.squarify(normed, 0, 0, 100, 100)
    
    for i, (rect, (_, row)) in enumerate(zip(rects, heatmap_df.iterrows())):
        ax.add_patch(plt.Rectangle((rect['x'], rect['y']), rect['dx'], rect['dy'], facecolor=colors[i], edgecolor='white', linewidth=2, alpha=0.9))
        ratio = (rect['dx'] * rect['dy']) / 10000
        font_size = max(7, min(24, int(7 + (28 - 7) * np.sqrt(ratio))))
        sign = "+" if row['Өөрчлөлт'] > 0 else ""
        label = row['Тикер'] if ratio < 0.02 else f"{row['Тикер']}\n{sign}{row['Өөрчлөлт']}%\n{row['Дүн']:,.0f} ₮"
        ax.text(rect['x'] + rect['dx']/2, rect['y'] + rect['dy']/2, label, ha='center', va='center', fontsize=font_size, color='white', fontweight='bold')

    # Watermark
    fig.text(0.5, 0.5, 'Ganbayar Batsuuri', fontsize=40, color='grey', ha='center', va='center', alpha=0.15, rotation=30)

    plt.title(title, fontsize=16, fontweight='bold', pad=20)
    plt.xlim(0, 100)
    plt.ylim(0, 100)
    plt.axis('off')
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    plt.close()
    buf.seek(0)
    return buf

# ==========================================
# 5. TELEGRAM ИЛГЭЭХ ҮЙЛДЭЛУҮД
# ==========================================
def send_telegram_photo(photo_buf, caption=""):
    if not BOT_TOKEN: return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    requests.post(url, files={'photo': ('chart.png', photo_buf, 'image/png')}, data={'chat_id': CHANNEL, 'caption': caption})

def send_telegram_message(text):
    if not BOT_TOKEN: return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={'chat_id': CHANNEL, 'text': text, 'parse_mode': 'Markdown', 'disable_web_page_preview': True})

def main():
    print("🚀 Бот ажиллаж эхэллээ...\n")
    df, trade_date = fetch_mse_data()
    
    if not df.empty:
        summary_text = generate_summary_text(df, trade_date)
        send_telegram_message(summary_text)
        
        heatmap_buf = create_heatmap(df, f"МХБ НЭГДСЭН ЗУРАГ ({trade_date})")
        if heatmap_buf:
            send_telegram_photo(heatmap_buf, f"📊 МХБ-ийн хувьцааны арилжааны хөдөлгөөн")
        print("✅ МХБ-ийн пост амжилттай орлоо.")
    else:
        print("⚠️ МХБ өгөгдөл олдсонгүй.")

if __name__ == "__main__":
    main()

# ==========================================
# МХБ & COMEX ӨДРИЙН АРИЛЖААНЫ ТОЙМ - TELEGRAM BOT
# ==========================================
import os
import requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import squarify
import io
import re
import urllib3
import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import asyncio
from playwright.async_api import async_playwright

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# 1. ТОХИРГОО
# ==========================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL = os.getenv("CHANNEL", "@openburry")

plt.rcParams['font.family'] = 'DejaVu Sans'
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# ==========================================
# 2. МХБ - ВИРТУАЛ ХӨТЧӨӨР ӨГӨГДӨЛ ТАТАХ
# ==========================================
async def fetch_mse_html_async():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://mse.mn/todays-trade", wait_until="networkidle")
        await page.wait_for_timeout(3000) # Хүснэгт зурагдахыг хүлээх
        html = await page.content()
        await browser.close()
        return html

def fetch_mse_data():
    print("🌐 Виртуал хөтчөөр (Playwright) MSE-ээс мэдээлэл татаж байна...")
    try:
        html = asyncio.run(fetch_mse_html_async())
    except Exception as e:
        print(f"❌ Виртуал хөтөч нээхэд алдаа гарлаа: {e}")
        return None, None
    
    trade_date = "Өнөөдрийн"
    date_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', html)
    if date_match:
        y, m, d = date_match.groups()
        trade_date = f"{y} оны {int(m)} дүгээр сарын {int(d)}-ны өдрийн"

    try: 
        dfs = pd.read_html(io.StringIO(html))
    except ValueError: return None, None

    stock_tables = [df for df in dfs if 'симбол' in " ".join(str(c).lower() for c in df.columns) or 'symbol' in " ".join(str(c).lower() for c in df.columns)]
    categories = {"I": None, "II": None, "III": None, "Сан": None}
    keys = list(categories.keys())
    for i, df in enumerate(stock_tables):
        if i < len(keys): categories[keys[i]] = df
            
    if not stock_tables: return None, None
    return categories, trade_date

# ==========================================
# 3. МХБ - МЭДЭЭЛЭЛ ЦЭВЭРЛЭХ & ТООЦООЛОХ
# ==========================================
def clean_df(df):
    if df is None or df.empty: return pd.DataFrame()
    cols = [" ".join(str(x).strip() for x in c if str(x).strip() and 'Unnamed' not in str(x)).lower() if isinstance(c, tuple) else str(c).strip().lower() for c in df.columns]
    df.columns = cols
    
    symbol_col = next((c for c in df.columns if 'симбол' in c or 'symbol' in c), None)
    amount_col = next((c for c in df.columns if 'мөнгөн дүн' in c or 'үнийн дүн' in c), None)
    qty_col = next((c for c in df.columns if 'ширхэг' in c or 'quantity' in c), None)
    prev_col = next((c for c in df.columns if 'өмнөх' in c), None)
    close_col = next((c for c in df.columns if 'хаалтын' in c), None)
    
    if not symbol_col or not amount_col: return pd.DataFrame()
    
    def parse_amount(val):
        if pd.isna(val) or str(val).strip() == '-': return 0.0
        match = re.search(r'-?\d+\.?\d*', str(val).replace(',', '').replace(' ', ''))
        return float(match.group()) if match else 0.0
            
    res = pd.DataFrame()
    res['Тикер'] = df[symbol_col].astype(str)
    res['Дүн'] = df[amount_col].apply(parse_amount)
    res['Ширхэг'] = df[qty_col].apply(parse_amount) if qty_col else 0.0
    
    if prev_col and close_col:
        prev_prices = df[prev_col].apply(parse_amount)
        close_prices = df[close_col].apply(parse_amount)
        res['Өөрчлөлт'] = np.where(prev_prices > 0, ((close_prices - prev_prices) / prev_prices) * 100, 0.0)
        res['Өөрчлөлт'] = res['Өөрчлөлт'].round(2)
    else: res['Өөрчлөлт'] = 0.0
    
    res = res[~res['Тикер'].isin(['nan', 'None', ''])]
    return res[res['Дүн'] > 0]

# ==========================================
# 4. МХБ - ЗУРАГ БЭЛТГЭХ
# ==========================================
def create_heatmap(df, title):
    if df.empty: return None
    fig, ax = plt.subplots(figsize=(12, 9))
    colors = ['#2ca02c' if c > 0 else '#d62728' if c < 0 else '#7f7f7f' for c in df['Өөрчлөлт']]
    normed = squarify.normalize_sizes(df['Дүн'].values, 100, 100)
    rects = squarify.squarify(normed, 0, 0, 100, 100)
    
    for i, (rect, (_, row)) in enumerate(zip(rects, df.iterrows())):
        ax.add_patch(plt.Rectangle((rect['x'], rect['y']), rect['dx'], rect['dy'], facecolor=colors[i], edgecolor='white', linewidth=2, alpha=0.9))
        ratio = (rect['dx'] * rect['dy']) / 10000
        font_size = max(7, min(24, int(7 + (28 - 7) * np.sqrt(ratio))))
        sign = "+" if row['Өөрчлөлт'] > 0 else ""
        label = row['Тикер'] if ratio < 0.02 else f"{row['Тикер']}\n{sign}{row['Өөрчлөлт']}%\n{row['Дүн']:,.0f} ₮"
        ax.text(rect['x'] + rect['dx']/2, rect['y'] + rect['dy']/2, label, ha='center', va='center', fontsize=font_size, color='white', fontweight='bold')

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

def create_summary_chart(cleaned_dfs, trade_date):
    amounts = {k: v['Дүн'].sum() for k, v in cleaned_dfs.items() if not v.empty}
    if not amounts: return None
    plt.figure(figsize=(8, 6))
    bars = plt.bar(amounts.keys(), amounts.values(), color=['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728'])
    plt.title(f"Арилжааны бүтэц\n({trade_date})", fontsize=14, fontweight='bold')
    plt.ylabel("Мөнгөн дүн (₮)")
    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2, yval, f"{yval:,.0f} ₮", ha='center', va='bottom', fontweight='bold')
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    plt.close()
    buf.seek(0)
    return buf

# ==========================================
# 5. МХБ - ТЕКСТ ТОЙМ БЭЛТГЭХ
# ==========================================
def generate_summary_text(cleaned_dfs, trade_date):
    total_amount = sum(df['Дүн'].sum() for df in cleaned_dfs.values() if not df.empty)
    total_qty = sum(df['Ширхэг'].sum() for df in cleaned_dfs.values() if not df.empty)
    stocks = pd.concat([cleaned_dfs['I'], cleaned_dfs['II'], cleaned_dfs['III']])
    
    text = f"📊 *МХБ — {trade_date.upper()} АРИЛЖААНЫ ТОЙМ*\n\n💰 Нийт арилжаа: {total_amount:,.0f} ₮\n📦 Нийт хувьцаа: {total_qty:,.0f} ширхэг\n\n"
    if not stocks.empty:
        top10 = stocks.sort_values('Дүн', ascending=False).head(10)
        text += "🏆 *Хамгийн их үнийн дүнтэй TOP 10:*\n"
        for i, (_, r) in enumerate(top10.iterrows(), 1): text += f"{i}. {r['Тикер']} — {r['Дүн']:,.0f} ₮\n"
            
        gainers = stocks[stocks['Өөрчлөлт'] > 0].sort_values('Өөрчлөлт', ascending=False).head(3)
        losers = stocks[stocks['Өөрчлөлт'] < 0].sort_values('Өөрчлөлт', ascending=True).head(3)
        if not gainers.empty:
            text += "\n📈 *Хамгийн их өсөлттэй:*\n"
            for _, r in gainers.iterrows(): text += f"🟩 {r['Тикер']} +{r['Өөрчлөлт']}%\n"
        if not losers.empty:
            text += "\n📉 *Хамгийн их бууралттай:*\n"
            for _, r in losers.iterrows(): text += f"🟥 {r['Тикер']} {r['Өөрчлөлт']}%\n"
            
    funds = cleaned_dfs['Сан']
    if funds is not None and not funds.empty:
        text += f"\n🏦 *Хөрөнгө оруулалтын сан:*\n▪️ Сангийн тоо: {len(funds)}\n▪️ Арилжаалсан нэгж эрх: {funds['Ширхэг'].sum():,.0f}\n▪️ Нийт үнийн дүн: {funds['Дүн'].sum():,.0f} ₮\n"
    return text

# ==========================================
# 6. COMEX - ХҮСНЭГТ ЗАДАЛЖ УНШИХ
# ==========================================
def parse_comex_table(url, date_str):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20, verify=False)
        dfs = pd.read_html(io.StringIO(r.text), header=None)
        if not dfs: return None
        df = dfs[0].dropna(how='all')
        
        trades = []
        total_tons = 0
        total_usd = 0
        total_cny = 0
        
        for col in range(1, len(df.columns)):
            info = {}
            for _, row in df.iterrows():
                key = str(row[0]).lower()
                val = str(row[col])
                if val == 'nan' or val == 'None': continue
                
                if 'худалдагч' in key and 'нэр' in key: info['company'] = val
                elif 'ангилал' in key: info['type'] = val.split('/')[0].strip()
                elif 'хэлцэл хийгдсэн үнэ' in key: info['price'] = val
                elif 'өсөлтийн хувь' in key: info['growth'] = val
                elif 'нийт үнийн дүн' in key:
                    info['total'] = val
                    amt_m = re.search(r'([\d,\.]+)\s*(USD|CNY|MNT)', val, re.IGNORECASE)
                    if amt_m:
                        amt = float(amt_m.group(1).replace(',', ''))
                        cur = amt_m.group(2).upper()
                        if cur == 'USD': total_usd += amt
                        if cur == 'CNY': total_cny += amt
                elif 'хэмжээ' in key and 'тонн' in key:
                    ton_m = re.search(r'(\d+)\s*тонн', val, re.IGNORECASE)
                    if ton_m:
                        tons = float(ton_m.group(1))
                        info['tons'] = tons
                        total_tons += tons
                        
            if 'company' in info: trades.append(info)
            
        text = f"📊 *COMEX — {date_str} АРИЛЖААНЫ ТОЙМ*\n\n"
        text += f"📦 *Нийт борлуулалт:* {total_tons:,.0f} тонн\n"
        
        val_strs = []
        if total_usd > 0: val_strs.append(f"${total_usd / 1e6:,.1f} сая")
        if total_cny > 0: val_strs.append(f"{total_cny / 1e6:,.1f} сая CNY")
        if val_strs: text += f"💰 *Үнийн дүн:* {' | '.join(val_strs)}\n"
        text += "\n" + "—"*20 + "\n\n"
        
        emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
        for i, t in enumerate(trades):
            emoji = emojis[i] if i < len(emojis) else "🔹"
            comp = t.get('company', 'Тодорхойгүй')
            typ = t.get('type', 'Бүтээгдэхүүн')
            qty = t.get('tons', 0)
            price = t.get('price', '-')
            growth = str(t.get('growth', '0%'))
            
            if '0%' in growth or growth == '0': growth_str = "➖ Өөрчлөлтгүй"
            elif '-' in growth: growth_str = f"▼ {growth} буурсан"
            else: growth_str = f"▲ +{growth.replace('+','')} өссөн"
                
            item_total = t.get('total', '-')
            amt_m = re.search(r'([\d,\.]+)\s*(USD|CNY|MNT)', item_total, re.IGNORECASE)
            if amt_m:
                amt = float(amt_m.group(1).replace(',', ''))
                cur = amt_m.group(2).upper()
                if cur == 'USD': item_total = f"${amt / 1e6:,.1f} сая"
                elif cur == 'CNY': item_total = f"{amt / 1e6:,.1f} сая CNY"
            
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
    print("\n🔎 COMEX шалгаж байна...")
    url = "https://comex.mse.mn/show_trading_infos"
    today = datetime.datetime.now()
    target_date_str = f"{today.month:02d}-р сарын {today.day:02d} өдрийн"
    
    try:
        r = requests.get(url, headers=HEADERS, timeout=20, verify=False)
        if r.status_code != 200: return None
        soup = BeautifulSoup(r.text, 'html.parser')
        
        for a in soup.find_all('a', href=True):
            title = re.sub(r"\s+", " ", a.get_text()).strip()
            title_lower = title.lower()
            if title_lower == "арилжааны мэдээлэл" or len(title) < 20: continue
                
            if "уул уурхайн бүтээгдэхүүний арилжааны мэдээ" in title_lower and target_date_str.lower() in title_lower:
                link = urljoin("https://comex.mse.mn", a['href'])
                date_formatted = today.strftime("%Y.%m.%d")
                
                print(f"   ✅ Мэдээ олдсон. Хүснэгт татаж байна...")
                parsed_text = parse_comex_table(link, date_formatted)
                
                if parsed_text: return parsed_text
                return f"📊 *COMEX (Уул уурхай)*\n\n{title}\n\n🔗 [Дэлгэрэнгүй унших]({link})"
    except Exception as e:
        print(f"❌ COMEX алдаа: {e}")
    return None

# ==========================================
# 7. TELEGRAM-Д ИЛГЭЭХ & ҮНДСЭН ҮЙЛДЭЛ
# ==========================================
def send_telegram_photo(photo_buf, caption=""):
    if not BOT_TOKEN:
        print("АЛДАА: BOT_TOKEN олдсонгүй!")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    requests.post(url, files={'photo': ('chart.png', photo_buf, 'image/png')}, data={'chat_id': CHANNEL, 'caption': caption})

def send_telegram_message(text):
    if not BOT_TOKEN:
        print("АЛДАА: BOT_TOKEN олдсонгүй!")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={'chat_id': CHANNEL, 'text': text, 'parse_mode': 'Markdown', 'disable_web_page_preview': True})

def main():
    print("🚀 Бот ажиллаж эхэллээ...\n")
    if not BOT_TOKEN:
        print("⚠️ АНХААР: BOT_TOKEN хоосон байна! Secrets тохиргоогоо шалгана уу.")
    
    # 1. МХБ МЭДЭЭЛЭЛ
    raw_data, trade_date = fetch_mse_data()
    if raw_data:
        print(f"🧹 МХБ Мэдээллийг боловсруулж байна... ({trade_date})")
        cleaned_dfs = {k: clean_df(v) for k, v in raw_data.items()}
        
        chart1 = create_summary_chart(cleaned_dfs, trade_date)
        if chart1: send_telegram_photo(chart1, f"📊 {trade_date} арилжааны бүтэц")
        send_telegram_message(generate_summary_text(cleaned_dfs, trade_date))
        
        if not cleaned_dfs['I'].empty: send_telegram_photo(create_heatmap(cleaned_dfs['I'], f"I АНГИЛАЛ ({trade_date})"), "🟢 I ангиллын хөдөлгөөн")
        if not cleaned_dfs['II'].empty: send_telegram_photo(create_heatmap(cleaned_dfs['II'], f"II АНГИЛАЛ ({trade_date})"), "🔵 II ангиллын хөдөлгөөн")
        if not cleaned_dfs['III'].empty: send_telegram_photo(create_heatmap(cleaned_dfs['III'], f"III АНГИЛАЛ ({trade_date})"), "🟣 III ангиллын хөдөлгөөн")
        if not cleaned_dfs['Сан'].empty: send_telegram_photo(create_heatmap(cleaned_dfs['Сан'], f"ХӨРӨНГӨ ОРУУЛАЛТЫН САН ({trade_date})"), "🏦 Сангийн хөдөлгөөн")
        print("✅ МХБ-ийн 6 пост амжилттай орлоо.")

    # 2. COMEX МЭДЭЭЛЭЛ
    comex_msg = fetch_comex_news()
    if comex_msg:
        send_telegram_message(comex_msg)
        print("✅ COMEX мэдээ амжилттай орлоо.")
    else:
        print("⚠️ Өнөөдрийн COMEX мэдээ олдсонгүй.")
        
    print("\n🎉 БҮХ ҮЙЛДЭЛ ДУУСЛАА!")

if __name__ == "__main__":
    main()

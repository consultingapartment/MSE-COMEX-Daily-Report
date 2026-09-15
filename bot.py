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
import json
import urllib3
import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# 1. ТОХИРГОО
# ==========================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL = os.getenv("CHANNEL", "@openburry")

plt.rcParams['font.family'] = 'DejaVu Sans'
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# ==========================================
# 2. МХБ - API (Next.js Payload)-аас дата шууд татах
# ==========================================
def fetch_mse_data():
    print("🌐 МХБ-ийн датаг далд API өгөгдлөөс татаж байна...")
    url = "https://mse.mn/todays-trade"
    try:
        r = requests.get(url, headers=HEADERS, verify=False, timeout=20)
        html = r.text
    except Exception as e:
        print(f"❌ МХБ сайттай холбогдоход алдаа гарлаа: {e}")
        return pd.DataFrame(), "Өнөөдрийн"
        
    # Огноо олох
    trade_date = "Өнөөдрийн"
    date_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', html)
    if date_match:
        y, m, d = date_match.groups()
        trade_date = f"{y} оны {int(m)} дүгээр сарын {int(d)}-ны өдрийн"

    # Next.js payload-аас шууд хувьцаа/бондын датаг шүүж авах (Regex ашиглан)
    # Nested биш хавтгай JSON объект тул хамгийн найдвартай арга нь энэ юм
    pattern = r'\{[^{}]*?"(?:companySymbol|bondSymbol)"[^{}]*?\}'
    matches = re.findall(pattern, html)
    
    data = []
    for m in matches:
        try:
            # HTML escape цэвэрлэх
            clean_json = m.replace('\\"', '"').replace('\\\\', '\\')
            obj = json.loads(clean_json)
            
            ticker = obj.get("companySymbol") or obj.get("bondSymbol", "Тодорхойгүй")
            turnover_str = str(obj.get("Turnover", "0")).replace(",", "").replace(" ", "")
            volume_str = str(obj.get("Volume", "0")).replace(",", "").replace(" ", "")
            change = float(obj.get("changePercentage", 0))
            
            turnover = float(turnover_str) if turnover_str else 0.0
            volume = float(volume_str) if volume_str else 0.0
            
            if turnover > 0:
                data.append({
                    "Тикер": ticker,
                    "Дүн": turnover,
                    "Ширхэг": volume,
                    "Өөрчлөлт": change
                })
        except Exception:
            continue
            
    df = pd.DataFrame(data)
    
    # Хэрэв дата хоосон биш бол адилхан тикертэй (жишээ нь багцын арилжаа + энгийн) дүнг нэгтгэх
    if not df.empty:
        df = df.groupby(['Тикер', 'Өөрчлөлт'], as_index=False).agg({'Дүн': 'sum', 'Ширхэг': 'sum'})
        
    return df, trade_date

# ==========================================
# 3. МХБ - ЗУРАГ БЭЛТГЭХ
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
# 4. МХБ - ТЕКСТ ТОЙМ БЭЛТГЭХ
# ==========================================
def generate_summary_text(df, trade_date):
    if df.empty:
        return "📊 Өнөөдрийн арилжааны дата олдсонгүй эсвэл арилжаа явагдаагүй байна."
        
    total_amount = df['Дүн'].sum()
    total_qty = df['Ширхэг'].sum()
    
    text = f"📊 *МХБ — {trade_date.upper()} АРИЛЖААНЫ ТОЙМ*\n\n💰 Нийт арилжаа: {total_amount:,.0f} ₮\n📦 Нийт хувьцаа, үнэт цаас: {total_qty:,.0f} ширхэг\n\n"
    
    top10 = df.sort_values('Дүн', ascending=False).head(10)
    text += "🏆 *Хамгийн их үнийн дүнтэй TOP 10:*\n"
    for i, (_, r) in enumerate(top10.iterrows(), 1): 
        text += f"{i}. {r['Тикер']} — {r['Дүн']:,.0f} ₮\n"
            
    gainers = df[df['Өөрчлөлт'] > 0].sort_values('Өөрчлөлт', ascending=False).head(3)
    losers = df[df['Өөрчлөлт'] < 0].sort_values('Өөрчлөлт', ascending=True).head(3)
    
    if not gainers.empty:
        text += "\n📈 *Хамгийн их өсөлттэй:*\n"
        for _, r in gainers.iterrows(): text += f"🟩 {r['Тикер']} +{r['Өөрчлөлт']}%\n"
    if not losers.empty:
        text += "\n📉 *Хамгийн их бууралттай:*\n"
        for _, r in losers.iterrows(): text += f"🟥 {r['Тикер']} {r['Өөрчлөлт']}%\n"
            
    return text

# ==========================================
# 5. COMEX - ХҮСНЭГТ ЗАДАЛЖ УНШИХ
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
# 6. TELEGRAM-Д ИЛГЭЭХ & ҮНДСЭН ҮЙЛДЭЛ
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
    mse_df, trade_date = fetch_mse_data()
    
    if not mse_df.empty:
        print(f"🧹 МХБ Мэдээллийг боловсруулж байна... ({trade_date})")
        
        # Нийт арилжааны текст мэдээлэл илгээх
        send_telegram_message(generate_summary_text(mse_df, trade_date))
        
        # Бүх хувьцааны Heatmap зураг
        heatmap_buf = create_heatmap(mse_df, f"МХБ НЭГДСЭН ЗУРАГ ({trade_date})")
        if heatmap_buf:
            send_telegram_photo(heatmap_buf, f"📊 МХБ-ийн бүх арилжааны хөдөлгөөн")
                
        print("✅ МХБ-ийн пост амжилттай орлоо.")

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

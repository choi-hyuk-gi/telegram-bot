import requests
from bs4 import BeautifulSoup
import time
import threading
from datetime import datetime, timedelta
import sys

# --- [정보 설정] ---
TOKEN = '8131864943:AAEE77BmAVdTqP06T2JcqIxhTKlCIemc-Ak'
CHAT_ID = '6991113379'
SERVICE_KEY = 'c2830ec3b623040f9ac01cb9a3980d1c3f6c949e9f4bd765adbfb2432c43b4ed'

seen_instagram = set()
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# 1. 나라장터
def get_info():
    msg = "📋 [최신 폴리싱 정보 조회]\n\n🏛️ 나라장터 (최근 6개월)\n"
    try:
        end_date = datetime.now().strftime('%Y%m%d0000')
        start_date = (datetime.now() - timedelta(days=180)).strftime('%Y%m%d0000')
        url = 'http://apis.data.go.kr/1230000/BidPublicInfoService05/getBidPblancListInfoSrschr01'
        params = {'serviceKey': SERVICE_KEY, 'numOfRows': '5', 'pageNo': '1', 'inqryDiv': '1', 'bidNtceNm': '폴리싱', 'bidNtceBgnDt': start_date, 'bidNtceEndDt': end_date, 'type': 'json'}
        
        res = requests.get(url, params=params, timeout=15)
        if "SERVICE KEY" in res.text:
            msg += "⚠️ API 키 승인 대기 중\n"
        else:
            items = res.json().get('response', {}).get('body', {}).get('items', [])
            if items:
                for i in items[:3]: msg += f"• {i.get('bidNtceNm')}\n   🔗 {i.get('bidNtceDtlUrl')}\n"
            else: msg += "• 검색된 공고가 없습니다.\n"
    except Exception as e: msg += f"• 접속 오류: {str(e)[:10]}...\n"

    msg += "\n🔥 인기통 최근 게시글\n"
    try:
        res = requests.get("http://www.inkitong.com/bbs/board.php?bo_table=guest&stx=폴리싱", headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        posts = soup.select('.td_subject a')[:3]
        if posts:
            for p in posts: msg += f"• {p.text.strip()}\n   🔗 {p['href']}\n"
        else: msg += "• 새 글이 없습니다."
    except Exception as e: msg += f"• 인기통 연결 실패: {str(e)[:10]}..."
    return msg

# 2. 경제 요약
def get_economy():
    urls = [
        ("🏠 부동산 주요사항", "https://www.mk.co.kr/rss/50300001/"),
        ("📈 미국주식/해외선물", "https://www.mk.co.kr/rss/30300001/")
    ]
    msg = "📊 [경제 핵심 요약 10선]\n"
    for title_head, url in urls:
        msg += f"\n{title_head}\n"
        try:
            res = requests.get(url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(res.content, 'xml')
            items = soup.find_all('item')[:5]
            if not items:
                soup = BeautifulSoup(res.content, 'html.parser')
                items = soup.find_all('item')[:5]
            
            for i, item in enumerate(items, 1):
                t = item.title.text
                d = item.description.text[:55].replace('<br>', ' ').strip() if item.description else ""
                msg += f"{i}. {t}\n   - {d}..\n"
        except: msg += "• 뉴스 가져오기 실패\n"
    return msg

# 3. 인스타그램
def check_instagram():
    global seen_instagram
    try:
        res = requests.get("https://imginn.org/tags/폴리싱문의/", headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        new_links = []
        for post in soup.select('.item'):
            link = "https://imginn.org" + post.find('a')['href']
            if link not in seen_instagram:
                new_links.append(link)
                seen_instagram.add(link)
        if new_links:
            msg = f"📸 [인스타그램 신규 문의 - {len(new_links)}건]\n"
            for i, link in enumerate(new_links, 1): msg += f"{i}. {link}\n"
            send_telegram(msg)
    except: pass

def send_telegram(text):
    try: requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage", params={"chat_id": CHAT_ID, "text": text}, timeout=10)
    except: pass

def instagram_timer():
    while True:
        check_instagram()
        time.sleep(3600) # 1시간마다

def monitor_commands():
    last_id = 0
    print("🚀 레일웨이 봇 시작!")
    send_telegram("🚀 레일웨이 서버에서 봇이 시작되었습니다!")
    while True:
        try:
            res = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates", params={"offset": last_id + 1, "timeout": 20}).json()
            for up in res.get("result", []):
                last_id = up["update_id"]
                txt = up.get("message", {}).get("text", "")
                if txt == "/?": send_telegram("❓ [도움말]\n/정보: 나라장터 & 인기통\n/경제: 뉴스 요약")
                elif txt == "/정보": send_telegram(get_info())
                elif txt == "/경제": send_telegram(get_economy())
            time.sleep(1)
        except: time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=instagram_timer, daemon=True).start()
    monitor_commands()

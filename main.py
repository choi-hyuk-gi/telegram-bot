import requests
from bs4 import BeautifulSoup
import time
import threading
from datetime import datetime, timedelta

# --- [설정 정보] ---
TOKEN = '8131864943:AAEE77BmAVdTqP06T2JcqIxhTKlCIemc-Ak'
CHAT_ID = '6991113379'
# 사장님 진짜 인증키 (그대로 두세요)
SERVICE_KEY = 'c2830ec3b623040f9ac01cb9a3980d1c3f6c949e9f4bd765adbfb2432c43b4ed'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# 1. 나라장터 & 인기통
def get_info():
    msg = "📋 [최신 폴리싱 정보]\n\n"
    
    # [나라장터]
    msg += "🏛️ 나라장터 (최근 6개월)\n"
    try:
        end_date = datetime.now().strftime('%Y%m%d0000')
        start_date = (datetime.now() - timedelta(days=180)).strftime('%Y%m%d0000')
        url = 'http://apis.data.go.kr/1230000/BidPublicInfoService05/getBidPblancListInfoSrschr01'
        
        params = {
            'serviceKey': SERVICE_KEY,
            'numOfRows': '5',
            'pageNo': '1',
            'inqryDiv': '1',
            'bidNtceNm': '폴리싱',
            'bidNtceBgnDt': start_date,
            'bidNtceEndDt': end_date,
            'type': 'json'
        }
        
        res = requests.get(url, params=params, timeout=30)
        
        if res.status_code != 200:
            msg += f"• 서버 점검 중 (코드: {res.status_code})\n"
        else:
            try:
                data = res.json()
                items = data.get('response', {}).get('body', {}).get('items', [])
                if items:
                    for i in items[:3]:
                        title = i.get('bidNtceNm', '제목없음')
                        link = i.get('bidNtceDtlUrl', '#')
                        msg += f"• {title}\n   🔗 {link}\n"
                else:
                    msg += "• 검색된 공고가 없습니다.\n"
            except:
                if "SERVICE KEY" in res.text or "REGISTERED" in res.text:
                    msg += "⚠️ 인증키 승인 대기 중 (1~2시간 소요)\n"
                else:
                    msg += "• 데이터 형식 오류 (잠시 후 다시 시도)\n"
    except Exception as e:
        msg += f"• 접속 실패: {str(e)[:15]}\n"

    # [인기통]
    msg += "\n🔥 인기통\n"
    msg += "• 해외 서버 차단으로 접속 불가 (VPN 필요)\n"
        
    return msg

# 2. 경제 뉴스 (구글 뉴스 - 무조건 뜹니다)
def get_economy():
    # 구글 뉴스 RSS (폴리싱/경제/건설)
    url = "https://news.google.com/rss/search?q=건설경기+OR+콘크리트&hl=ko&gl=KR&ceid=KR:ko"
    msg = "📊 [건설/경제 뉴스 (구글)]\n"
    
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(res.content, 'xml')
        items = soup.find_all('item')[:5]
        
        if not items:
            msg += "• 최신 뉴스가 없습니다.\n"
        
        for i, item in enumerate(items, 1):
            t = item.title.text
            l = item.link.text
            msg += f"{i}. {t}\n   🔗 {l}\n"
    except:
        msg += "• 뉴스를 가져오지 못했습니다.\n"
        
    return msg

# 3. 텔레그램 전송
def send_telegram(text):
    try:
        requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage", params={"chat_id": CHAT_ID, "text": text}, timeout=10)
    except:
        pass

# 4. 봇 실행
def monitor_commands():
    last_id = 0
    print("🚀 봇 최종 수정본 시작")
    send_telegram("🚀 봇 재시작 완료! 제목이 [건설/경제 뉴스]로 바뀌었는지 확인하세요.")
    
    while True:
        try:
            res = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates", params={"offset": last_id + 1, "timeout": 20}).json()
            for up in res.get("result", []):
                last_id = up["update_id"]
                txt = up.get("message", {}).get("text", "")
                
                if txt == "/?":
                    send_telegram("❓ [도움말]\n/정보: 나라장터 공고\n/경제: 건설 경기 뉴스")
                elif txt == "/정보":
                    send_telegram(get_info())
                elif txt == "/경제":
                    send_telegram(get_economy())
            time.sleep(1)
        except:
            time.sleep(5)

if __name__ == "__main__":
    monitor_commands()

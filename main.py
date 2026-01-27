import requests
from bs4 import BeautifulSoup
import time
import threading
from datetime import datetime, timedelta
import sys

# --- [정보 설정] ---
# 텔레그램 봇 토큰 및 아이디
TOKEN = '8131864943:AAEE77BmAVdTqP06T2JcqIxhTKlCIemc-Ak'
CHAT_ID = '6991113379'

# ★★★ [수정 완료] 작성자님이 주신 진짜 인증키입니다 ★★★
SERVICE_KEY = 'c2830ec3b623040f9ac01cb9a3980d1c3f6c949e9f4bd765adbfb2432c43b4ed'

seen_instagram = set()
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# 1. 나라장터 & 인기통 조회 함수
def get_info():
    msg = "📋 [최신 폴리싱 정보 조회]\n\n🏛️ 나라장터 (최근 6개월)\n"
    
    # [나라장터 로직]
    try:
        end_date = datetime.now().strftime('%Y%m%d0000')
        start_date = (datetime.now() - timedelta(days=180)).strftime('%Y%m%d0000')
        base_url = 'http://apis.data.go.kr/1230000/BidPublicInfoService05/getBidPblancListInfoSrschr01'
        
        # 중요: 인증키가 깨지지 않도록 URL에 직접 조립합니다.
        full_url = f"{base_url}?serviceKey={SERVICE_KEY}&numOfRows=5&pageNo=1&inqryDiv=1&bidNtceNm=폴리싱&bidNtceBgnDt={start_date}&bidNtceEndDt={end_date}&type=json"
        
        res = requests.get(full_url, timeout=30)
        
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
            # 키가 틀렸거나 데이터 형식이 다를 때 예외 처리
            if "SERVICE KEY" in res.text or "SERVICE_KEY" in res.text:
                msg += "⚠️ 인증키 에러: 아직 공공데이터포털 승인이 안 났거나 키 문제일 수 있습니다.\n"
            else:
                msg += "• 공고를 불러오는 중 오류가 발생했습니다.\n"
    except Exception as e:
        msg += f"• 접속 오류: {str(e)[:10]}...\n"

    # [인기통 로직]
    msg += "\n🔥 인기통 (최근 게시글)\n"
    try:
        # 해외 서버(Railway) 차단 대비 예외 처리
        res = requests.get("http://www.inkitong.com/bbs/board.php?bo_table=guest&stx=폴리싱", headers=HEADERS, timeout=5)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            posts = soup.select('.td_subject a')[:3]
            if posts:
                for p in posts:
                    title = p.text.strip()
                    link = p['href']
                    msg += f"• {title}\n   🔗 {link}\n"
            else:
                msg += "• 새 글이 없습니다.\n"
        else:
            msg += "• 사이트 접속 차단됨 (해외 IP 제한)\n"
    except:
        msg += "• 접속 실패 (서버 응답 없음)\n"
        
    return msg

# 2. 경제 뉴스 조회 함수
def get_economy():
    urls = [
        ("🏠 부동산 주요사항", "https://www.mk.co.kr/rss/50300001/"),
        ("📈 미국주식/해외선물", "https://www.mk.co.kr/rss/30300001/")
    ]
    msg = "📊 [경제 핵심 요약 10선]\n"
    for title_head, url in urls:
        msg += f"\n{title_head}\n"
        try:
            res = requests.get(url, headers=HEADERS, timeout=10)
            # RSS 파싱 시도 (XML -> HTML 순서)
            try:
                soup = BeautifulSoup(res.content, 'xml')
                items = soup.find_all('item')[:5]
            except:
                soup = BeautifulSoup(res.content, 'html.parser')
                items = soup.find_all('item')[:5]
            
            if not items:
                msg += "• 기사를 가져올 수 없습니다.\n"
                continue

            for i, item in enumerate(items, 1):
                t = item.title.text
                msg += f"{i}. {t}\n"
        except:
            msg += "• 뉴스 접속 실패\n"
    return msg

# 3. 텔레그램 전송 함수
def send_telegram(text):
    try:
        requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage", params={"chat_id": CHAT_ID, "text": text}, timeout=10)
    except:
        pass

# 4. 봇 실행 및 감시
def monitor_commands():
    last_id = 0
    print("🚀 레일웨이 봇 최종 수정본 시작!")
    send_telegram("🚀 봇 업데이트 완료! 이제 진짜 키로 정보를 가져옵니다.")
    
    while True:
        try:
            # 텔레그램 서버에서 메시지 가져오기
            res = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates", params={"offset": last_id + 1, "timeout": 20}).json()
            for up in res.get("result", []):
                last_id = up["update_id"]
                txt = up.get("message", {}).get("text", "")
                
                if txt == "/?":
                    send_telegram("❓ [도움말]\n/정보: 나라장터 & 인기통\n/경제: 뉴스 요약")
                elif txt == "/정보":
                    send_telegram(get_info())
                elif txt == "/경제":
                    send_telegram(get_economy())
            time.sleep(1)
        except:
            time.sleep(5)

if __name__ == "__main__":
    monitor_commands()

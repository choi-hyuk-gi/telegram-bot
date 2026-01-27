import requests
from bs4 import BeautifulSoup
import time
import threading
import random
from datetime import datetime, timedelta
import re

# --- [설정 정보] ---
TOKEN = '8131864943:AAEE77BmAVdTqP06T2JcqIxhTKlCIemc-Ak'
CHAT_ID = '6991113379'
# 사장님 인증키 (나라장터용)
SERVICE_KEY = 'c2830ec3b623040f9ac01cb9a3980d1c3f6c949e9f4bd765adbfb2432c43b4ed'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# 이미 본 인스타 게시물 저장용
seen_instagram = set()

# 1. 나라장터 (공사 공고)
def get_info():
    msg = "📋 [나라장터 공사 공고]\n"
    try:
        end_date = datetime.now().strftime('%Y%m%d0000')
        start_date = (datetime.now() - timedelta(days=180)).strftime('%Y%m%d0000')
        url = 'http://apis.data.go.kr/1230000/BidPublicInfoService/getBidPblancListInfoCnstwk'
        
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
                    for i in items[:5]: # 5개까지 표시
                        title = i.get('bidNtceNm', '제목없음')
                        link = i.get('bidNtceDtlUrl', '#')
                        date = i.get('bidNtceDt', '')[:10]
                        msg += f"• [{date}] {title}\n   🔗 {link}\n"
                else:
                    msg += "• 검색된 공고가 없습니다.\n"
            except:
                if "SERVICE KEY" in res.text:
                    msg += "⚠️ 키 승인 대기 중 (잠시 후 다시 시도)\n"
                else:
                    msg += "• 데이터 조회 실패\n"
    except Exception as e:
        msg += f"• 접속 오류: {str(e)[:15]}\n"
        
    return msg

# 2. 경제 뉴스 (부동산 & 주식 - 2줄 요약)
def get_economy():
    msg = ""
    
    # (1) 부동산 주요 뉴스
    msg += "🏠 [부동산 주요 뉴스 Top 5]\n"
    try:
        url = "https://news.google.com/rss/search?q=부동산+시장&hl=ko&gl=KR&ceid=KR:ko"
        res = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(res.content, 'xml')
        items = soup.find_all('item')[:5]
        
        for i, item in enumerate(items, 1):
            title = item.title.text
            # 설명 태그 제거 및 1줄 요약
            desc = BeautifulSoup(item.description.text, "html.parser").text[:60] + "..."
            msg += f"{i}. {title}\n   - {desc}\n"
    except:
        msg += "• 뉴스를 가져오지 못했습니다.\n"

    msg += "\n"

    # (2) 미국주식 & 해외선물
    msg += "📈 [미국주식 & 해외선물 Top 5]\n"
    try:
        url = "https://news.google.com/rss/search?q=미국주식+OR+해외선물&hl=ko&gl=KR&ceid=KR:ko"
        res = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(res.content, 'xml')
        items = soup.find_all('item')[:5]
        
        for i, item in enumerate(items, 1):
            title = item.title.text
            desc = BeautifulSoup(item.description.text, "html.parser").text[:60] + "..."
            msg += f"{i}. {title}\n   - {desc}\n"
    except:
        msg += "• 뉴스를 가져오지 못했습니다.\n"
        
    return msg

# 3. 인스타그램 (랜덤 딜레이 적용)
def check_instagram():
    global seen_instagram
    # 검색어: 콘크리트폴리싱 (태그 검색)
    url = "https://imginn.org/tags/콘크리트폴리싱/"
    
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 새 게시물 찾기
        new_posts = []
        items = soup.select('.item') # 게시물 목록
        
        for post in items[:5]: # 최신 5개만 확인
            try:
                link_tag = post.find('a')
                if link_tag:
                    link = "https://imginn.org" + link_tag['href']
                    # 이미지 설명(캡션) 가져오기 시도
                    caption = post.find('img')['alt'] if post.find('img') else "내용 없음"
                    
                    if link not in seen_instagram:
                        seen_instagram.add(link)
                        # '문의' 라는 단어가 있거나 처음 보는 글이면 알림
                        if "문의" in caption or "질문" in caption or len(seen_instagram) <= 5:
                            new_posts.append(f"📸 [인스타 새 글]\n{caption[:30]}...\n🔗 {link}")
            except:
                continue
                
        if new_posts:
            for p in new_posts:
                send_telegram(p)
                
    except Exception as e:
        print(f"인스타 접속 오류: {e}")

# 인스타그램 타이머 (사람인 척 랜덤 시간)
def instagram_timer():
    while True:
        check_instagram()
        
        # 1시간(3600초) + 0분~10분(0~600초) 랜덤 추가
        delay = 3600 + random.randint(0, 600)
        
        # 딜레이 시간 계산해서 로그 출력 (서버 기록용)
        next_time = datetime.now() + timedelta(seconds=delay)
        print(f"인스타 다음 확인: {next_time.strftime('%H:%M:%S')} (딜레이 {delay}초)")
        
        time.sleep(delay)

# 4. 텔레그램 전송
def send_telegram(text):
    try:
        requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage", params={"chat_id": CHAT_ID, "text": text}, timeout=10)
    except:
        pass

# 5. 봇 실행 및 명령어 감시
def monitor_commands():
    last_id = 0
    print("🚀 봇 최종 통합본 시작")
    send_telegram("🚀 봇 업데이트 완료!\n\n1. /정보 : 나라장터 공사\n2. /경제 : 부동산/주식 (2줄 요약)\n3. 인스타 : 1시간+@ 랜덤 간격 자동 감시 중")
    
    while True:
        try:
            res = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates", params={"offset": last_id + 1, "timeout": 20}).json()
            for up in res.get("result", []):
                last_id = up["update_id"]
                txt = up.get("message", {}).get("text", "")
                
                if txt == "/?":
                    send_telegram("❓ [메뉴]\n/정보 : 나라장터(공사)\n/경제 : 부동산, 주식 뉴스")
                elif txt == "/정보":
                    send_telegram(get_info())
                elif txt == "/경제":
                    send_telegram(get_economy())
            time.sleep(1)
        except:
            time.sleep(5)

if __name__ == "__main__":
    # 인스타그램 감시를 별도 쓰레드로 실행 (봇과 동시에 돔)
    threading.Thread(target=instagram_timer, daemon=True).start()
    monitor_commands()

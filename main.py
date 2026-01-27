import requests
from bs4 import BeautifulSoup
import time
import threading
import random
import json
from datetime import datetime, timedelta

# --- [설정 정보] ---
TOKEN = '8131864943:AAEE77BmAVdTqP06T2JcqIxhTKlCIemc-Ak'
OWNER_ID = '6991113379'

# 1. 나라장터 키
SERVICE_KEY = 'c2830ec3b623040f9ac01cb9a3980d1c3f6c949e9f4bd765adbfb2432c43b4ed'

# 2. 퍼플렉시티 키
PPLX_API_KEY = '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'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

seen_instagram = set()

# 텔레그램 전송
def send_telegram(text, target_id=None):
    if target_id is None: target_id = OWNER_ID
    try:
        requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage", params={"chat_id": target_id, "text": text}, timeout=10)
    except: pass

# --- [AI 기능: sonar-pro] ---
def ask_perplexity(system_role, user_prompt):
    url = "https://api.perplexity.ai/chat/completions"
    payload = {
        "model": "sonar-pro", 
        "messages": [
            { "role": "system", "content": system_role },
            { "role": "user", "content": user_prompt }
        ]
    }
    headers = { "Authorization": f"Bearer {PPLX_API_KEY}", "Content-Type": "application/json" }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        if response.status_code != 200: return f"🚨 [AI 오류] {response.text}"
        return response.json()['choices'][0]['message']['content']
    except Exception as e: return f"⚠️ [시스템 에러]: {str(e)}"

# 1. 나라장터 + 인기통 (필터링 강화)
def get_info():
    msg = "📋 [나라장터 & 인기통 정보]\n\n"
    
    # (1) 나라장터
    msg += "🏛️ [나라장터 공사 공고]\n"
    try:
        end_date = datetime.now().strftime('%Y%m%d0000')
        start_date = (datetime.now() - timedelta(days=180)).strftime('%Y%m%d0000')
        url = 'http://apis.data.go.kr/1230000/BidPublicInfoService/getBidPblancListInfoCnstwk'
        params = { 'serviceKey': SERVICE_KEY, 'numOfRows': '5', 'pageNo': '1', 'inqryDiv': '1', 'bidNtceNm': '폴리싱', 'bidNtceBgnDt': start_date, 'bidNtceEndDt': end_date, 'type': 'json' }
        res = requests.get(url, params=params, timeout=30)
        if res.status_code == 200:
            items = res.json().get('response', {}).get('body', {}).get('items', [])
            if items:
                for i in items[:5]:
                    msg += f"• [{i.get('bidNtceDt', '')[:10]}] {i.get('bidNtceNm', '제목없음')}\n   🔗 {i.get('bidNtceDtlUrl', '#')}\n"
            else: msg += "• 검색된 공고가 없습니다.\n"
        else: msg += f"• 정부 서버 점검 중 (코드: {res.status_code})\n"
    except: msg += f"• 접속 오류 (정부 서버 불안정)\n"

    msg += "\n--------------------------------\n\n"

    # (2) 인기통 (AI 필터링 강화: 도장/페인트/자동차 제외)
    msg += "🔥 [인기통/카페 폴리싱 구인]\n"
    prompt = (
        "사이트 'inkitong.com' 또는 '네이버 카페'에서 '콘크리트 폴리싱' 또는 '바닥 연마' 관련 최신 구인 글 3개를 찾아줘. "
        "조건 1: '도장', '페인트', '자동차', '도금', '생산직' 관련 글은 무조건 제외해. 오직 건설/바닥 현장만 찾아. "
        "조건 2: 결과는 '글 제목 - 링크' 형식으로 출력해."
    )
    msg += ask_perplexity("건설 구인 검색원", prompt)
    return msg

# 2. 경제 뉴스
def get_economy():
    real_estate = ask_perplexity("부동산 전문가", "한국 부동산 시장(매매/전세/정책) 최신 뉴스 5개. 2줄 요약.")
    stocks = ask_perplexity("주식 전문가", "미국 주식 및 해외 선물 최신 동향 5개. 2줄 요약.")
    return f"🏠 [부동산 Top 5]\n{real_estate}\n\n-----------------\n\n📈 [미국주식 Top 5]\n{stocks}"

# 3. 인스타그램 (AI가 찾아서 시간까지 표시)
def check_instagram_ai():
    # AI에게 최신 인스타 검색 요청 (시간 포함)
    prompt = (
        "인스타그램, Picuki, Imginn 같은 뷰어 사이트에서 '#콘크리트폴리싱' 태그의 최신 게시물 3개를 찾아줘. "
        "각 게시물의 '내용 요약', '링크', 그리고 '업로드 시간(예: <2시간 전>)'을 꼭 찾아서 표시해줘. "
        "오래된 글 말고 가장 최신 글 위주로."
    )
    result = ask_perplexity("SNS 검색 비서", prompt)
    
    # AI 결과를 사장님께 전송 (내용이 있을 때만)
    if "찾을 수 없습니다" not in result and len(result) > 20:
        send_telegram(f"📸 [인스타 최신 동향]\n{result}")

def instagram_timer():
    while True:
        # 1시간 + 랜덤 10분마다 실행
        check_instagram_ai()
        time.sleep(3600 + random.randint(0, 600))

def monitor_commands():
    last_id = 0
    print("🚀 AI 봇 시작")
    send_telegram("🚀 봇 업데이트 완료!\n1. 도장/페인트 글은 뺍니다.\n2. 인스타 글에 <시간>이 표시됩니다.")
    
    while True:
        try:
            res = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates", params={"offset": last_id + 1, "timeout": 20}).json()
            for up in res.get("result", []):
                last_id = up["update_id"]
                msg_data = up.get("message", {})
                text = msg_data.get("text", "")
                chat_id = msg_data.get("chat", {}).get("id")

                if not text: continue

                if text == "/?":
                    send_telegram("❓ 메뉴\n/정보: 나라장터 & 인기통(콘크리트 전용)\n/경제: 뉴스 브리핑", chat_id)
                elif text == "/정보":
                    send_telegram("🔍 콘크리트 폴리싱 정보만 골라내는 중...", chat_id)
                    send_telegram(get_info(), chat_id)
                elif text == "/경제":
                    send_telegram("🤖 뉴스를 분석 중입니다...", chat_id)
                    send_telegram(get_economy(), chat_id)
                elif text == "/id":
                    send_telegram(f"🆔 방 ID: {chat_id}", chat_id)
            time.sleep(1)
        except: time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=instagram_timer, daemon=True).start()
    monitor_commands()

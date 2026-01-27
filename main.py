import requests
from bs4 import BeautifulSoup
import time
import threading
import random
import json
from datetime import datetime, timedelta

# --- [설정 정보] ---
TOKEN = '8131864943:AAEE77BmAVdTqP06T2JcqIxhTKlCIemc-Ak'

# ★ 사장님 개인 ID (비상용)
OWNER_ID = '6991113379'
# ★ 단톡방 ID (자동 알림은 여기로 감)
GROUP_ID = '-4663839015'

# 1. 나라장터 키
SERVICE_KEY = 'c2830ec3b623040f9ac01cb9a3980d1c3f6c949e9f4bd765adbfb2432c43b4ed'

# 2. 퍼플렉시티 키
PPLX_API_KEY = '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'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

seen_instagram = set()

# 텔레그램 전송 (target_id가 없으면 단톡방으로 보냄)
def send_telegram(text, target_id=None):
    if target_id is None: 
        target_id = GROUP_ID # 기본 목적지를 단톡방으로 변경
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

# 1. 나라장터 + 인기통 (기존 유지: 도장 제외)
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

    # (2) 인기통 (AI 필터링)
    msg += "🔥 [인기통/카페 폴리싱 구인]\n"
    prompt = (
        "사이트 'inkitong.com' 또는 '네이버 카페'에서 '콘크리트 폴리싱' 또는 '바닥 연마' 관련 최신 구인 글 3개를 찾아줘. "
        "조건 1: '도장', '페인트', '자동차', '도금', '생산직' 관련 글은 무조건 제외해. 오직 건설/바닥 현장만 찾아. "
        "조건 2: 결과는 '글 제목 - 링크' 형식으로 출력해."
    )
    msg += ask_perplexity("건설 구인 검색원", prompt)
    return msg

# 2. 경제 뉴스 (기존 유지)
def get_economy():
    real_estate = ask_perplexity("부동산 전문가", "한국 부동산 시장(매매/전세/정책) 최신 뉴스 5개. 2줄 요약.")
    stocks = ask_perplexity("주식 전문가", "미국 주식 및 해외 선물 최신 동향 5개. 2줄 요약.")
    return f"🏠 [부동산 Top 5]\n{real_estate}\n\n-----------------\n\n📈 [미국주식 Top 5]\n{stocks}"

# 3. 인스타그램 (★ 문의 댓글 사냥꾼 모드 ★)
def check_instagram_ai():
    # AI에게 한국어 문의 댓글 위주 검색 요청
    prompt = (
        "인스타그램(Instagram) 또는 한국 소셜미디어에서 '#콘크리트폴리싱' 또는 '#바닥시공' 태그를 검색해줘. "
        "단순 홍보글은 무시하고, **'댓글(Comment)'이나 '본문'에 다음과 같은 내용이 있는 글만 3개 찾아줘:**\n"
        "1. '견적 문의합니다' (Quote inquiry)\n"
        "2. '비용이 어떻게 되나요?' (Price inquiry)\n"
        "3. '지역이 어디세요?' (Location inquiry)\n"
        "4. 'DM 주세요' or '연락처 좀'\n"
        "**반드시 '한국어(Korean)' 게시물이어야 함.**\n"
        "결과 출력 형식:\n"
        "- 📝 문의 내용: (댓글이나 본문의 문의 내용 요약)\n"
        "- 🔗 링크: (URL)\n"
        "- ⏰ 시간: (예: <3시간 전>)"
    )
    result = ask_perplexity("SNS 영업 비서", prompt)
    
    # 결과가 유효하면 단톡방으로 전송
    if "찾을 수 없습니다" not in result and len(result) > 20:
        send_telegram(f"📸 [인스타 견적 문의 감지]\n{result}", GROUP_ID)

def instagram_timer():
    while True:
        # 1시간 + 랜덤 10분마다 실행
        check_instagram_ai()
        time.sleep(3600 + random.randint(0, 600))

def monitor_commands():
    last_id = 0
    print("🚀 단톡방 봇 시작")
    # 시작 알림을 단톡방으로 쏘기
    send_telegram("🚀 봇 업데이트 완료!\n1. 이제 인스타에서 '견적/비용 문의' 댓글만 콕 집어 찾아냅니다.\n2. 알림은 이 단톡방으로 자동 전송됩니다.", GROUP_ID)
    
    while True:
        try:
            res = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates", params={"offset": last_id + 1, "timeout": 20}).json()
            for up in res.get("result", []):
                last_id = up["update_id"]
                msg_data = up.get("message", {})
                text = msg_data.get("text", "")
                chat_id = msg_data.get("chat", {}).get("id")

                if not text: continue

                # 명령어 처리 (누가 물어보든 그 방에 대답)
                if text == "/?":
                    send_telegram("❓ 메뉴\n/정보: 나라장터 & 인기통(콘크리트 전용)\n/경제: 뉴스 브리핑", chat_id)
                elif text == "/정보":
                    send_telegram("🔍 콘크리트 폴리싱 정보만 골라내는 중...", chat_id)
                    send_telegram(get_info(), chat_id)
                elif text == "/경제":
                    send_telegram("🤖 뉴스를 분석 중입니다...", chat_id)
                    send_telegram(get_economy(), chat_id)
                elif text == "/id":
                    send_telegram(f"🆔 이 방의 ID: {chat_id}", chat_id)
            time.sleep(1)
        except: time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=instagram_timer, daemon=True).start()
    monitor_commands()

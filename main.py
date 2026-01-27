import requests
import time
import threading
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

# 텔레그램 전송
def send_telegram(text, target_id=None):
    if target_id is None: 
        target_id = GROUP_ID # 기본 목적지를 단톡방으로 설정
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

# 1. 나라장터 + 인기통 (기존 유지)
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

# 3. [NEW] 웹 리드 자동 검색 (네이버/다음/웹문서)
def check_web_leads():
    # 검색할 키워드 정의
    keywords = [
        "콘크리트 폴리싱 견적", "바닥 면갈이 업체", "도끼다시 연마 광택", 
        "에폭시 제거후 폴리싱", "테라조 복원 비용", "상가바닥 노출 콘크리트 시공"
    ]
    keywords_str = ", ".join(keywords)

    # AI에게 보낼 프롬프트 (24시간 이내, 견적/추천 위주)
    prompt = (
        f"네이버 블로그, 네이버 카페, 다음 카페, 그리고 웹문서에서 최근 24시간 이내에 올라온 글을 검색해줘. "
        f"검색 키워드는 다음과 같아: {keywords_str}. "
        "**가장 중요한 필터링 조건:**\n"
        "1. 단순 광고글은 제외하고, **'견적 문의', '비용 질문', '업체 추천 요청'** 등 실제 고객의 수요가 있는 글만 찾아줘.\n"
        "2. 반드시 **최근 24시간 이내(Latest 24 hours)** 작성된 글이어야 해.\n"
        "3. 유의미한 정보가 없다면 '최근 24시간 내 유의미한 견적 문의가 없습니다.'라고 답해줘.\n\n"
        "**출력 형식 (글이 있을 경우 3개까지):**\n"
        "1. [출처] 글 제목\n"
        "   - 📝 요약: (고객이 무엇을 원하는지 핵심 요약)\n"
        "   - 🔗 링크: (URL)\n"
    )
    
    result = ask_perplexity("온라인 영업 비서", prompt)
    
    # 결과가 너무 짧거나(없음), 에러가 아니면 전송
    if "없습니다" not in result and len(result) > 30:
        send_telegram(f"📢 [실시간 웹 견적문의 감지]\n{result}", GROUP_ID)
    else:
        # (선택사항) 문의가 없어도 로그를 보고 싶으시면 아래 주석을 해제하세요.
        # print("-> 검색 결과 없음")
        pass

def web_lead_timer():
    print("⏳ 웹 리드 검색 타이머 시작 (1시간 간격)")
    while True:
        check_web_leads()
        # 정확히 1시간 (3600초) 대기 (랜덤 없음)
        time.sleep(3600)

def monitor_commands():
    last_id = 0
    print("🚀 단톡방 봇 시작 - 모드: 웹 리드 발굴")
    send_telegram("🚀 봇 업데이트 완료!\n1. 인스타 기능 OFF -> 네이버/다음/웹문서 견적 탐색 ON\n2. '콘크리트 폴리싱 견적' 등 핵심 키워드로 24시간 내 문의글을 1시간마다 자동 보고합니다.", GROUP_ID)
    
    while True:
        try:
            res = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates", params={"offset": last_id + 1, "timeout": 20}).json()
            for up in res.get("result", []):
                last_id = up["update_id"]
                msg_data = up.get("message", {})
                text = msg_data.get("text", "")
                chat_id = msg_data.get("chat", {}).get("id")

                if not text: continue

                # 명령어 처리
                if text == "/?":
                    send_telegram("❓ 메뉴\n/정보: 나라장터 & 인기통(콘크리트 전용)\n/경제: 뉴스 브리핑\n(자동): 매 1시간마다 웹 견적문의 리포트", chat_id)
                elif text == "/정보":
                    send_telegram("🔍 공고 및 구인 정보를 찾고 있습니다...", chat_id)
                    send_telegram(get_info(), chat_id)
                elif text == "/경제":
                    send_telegram("🤖 뉴스를 분석 중입니다...", chat_id)
                    send_telegram(get_economy(), chat_id)
                elif text == "/id":
                    send_telegram(f"🆔 이 방의 ID: {chat_id}", chat_id)
            time.sleep(1)
        except: time.sleep(5)

if __name__ == "__main__":
    # 타이머 스레드 시작 (메인 로직과 별개로 1시간마다 돔)
    threading.Thread(target=web_lead_timer, daemon=True).start()
    # 봇 명령 감시 시작
    monitor_commands()

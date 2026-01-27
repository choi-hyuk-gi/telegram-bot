import requests
import time
import threading
import json
import re
from datetime import datetime, timedelta

# --- [설정 정보] ---
TOKEN = '8131864943:AAEE77BmAVdTqP06T2JcqIxhTKlCIemc-Ak'
OWNER_ID = '6991113379'
GROUP_ID = '-4663839015' 

# 1. 나라장터 키
SERVICE_KEY = 'c2830ec3b623040f9ac01cb9a3980d1c3f6c949e9f4bd765adbfb2432c43b4ed'

# 2. 퍼플렉시티 키
PPLX_API_KEY = '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'

# 3. 네이버 API 키 (사장님 키)
NAVER_CLIENT_ID = '7D1q3B5fpC5O4fxVGNmD'
NAVER_CLIENT_SECRET = 'ffJg82MJO2'

# 이미 본 글은 다시 안 보냄 (중복 방지)
seen_links = set()

# 텔레그램 전송
def send_telegram(text, target_id=None):
    if target_id is None: target_id = GROUP_ID
    try:
        requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage", params={"chat_id": target_id, "text": text}, timeout=10)
    except: pass

# --- [AI 기능] ---
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
        if response.status_code != 200: return None
        return response.json()['choices'][0]['message']['content']
    except: return None

# --- [네이버 검색 엔진] ---
def search_naver(query):
    results = []
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    # 블로그(blog), 카페(cafearticle), 웹문서(webkr)
    for category in ['blog', 'cafearticle', 'webkr']:
        url = f"https://openapi.naver.com/v1/search/{category}.json"
        params = { "query": query, "display": 5, "start": 1, "sort": "date" }
        try:
            res = requests.get(url, headers=headers, params=params, timeout=5)
            if res.status_code == 200:
                items = res.json().get('items', [])
                for item in items:
                    clean_title = re.sub('<.*?>', '', item['title'])
                    clean_desc = re.sub('<.*?>', '', item['description'])
                    link = item['link']
                    results.append({'title': clean_title, 'desc': clean_desc, 'link': link, 'source': category})
        except: pass
    return results

# --- [핵심: 돌 바닥 전용 감시] ---
def check_naver_leads_smart():
    global seen_links
    
    # ★ 수정됨: 마루/후로링 제외하고 콘크리트/석재 위주로 세팅
    keywords = [
        "콘크리트 폴리싱 견적", "바닥 면갈이 업체", "도끼다시 연마 광택", 
        "에폭시 제거후 폴리싱", "테라조 복원 비용", "상가바닥 노출 콘크리트 시공",
        "학교 도끼다시 연마", "학교 테라조 공사", # 학교는 돌 바닥만
        "관공서 바닥 면갈이"
    ]
    
    raw_leads = []
    for key in keywords:
        items = search_naver(key)
        for item in items:
            if item['link'] not in seen_links:
                raw_leads.append(item)
                seen_links.add(item['link'])

    if not raw_leads:
        # print("-> 새 글 없음")
        return

    # AI에게 보낼 데이터
    candidates = raw_leads[:15]
    
    prompt_text = "다음은 웹에서 수집한 바닥 공사 관련 최신 글입니다.\n\n"
    for i, lead in enumerate(candidates):
        prompt_text += f"{i+1}. [{lead['source']}] 제목: {lead['title']}\n   내용: {lead['desc']}\n   링크: {lead['link']}\n\n"
        
    prompt_text += (
        "**지시사항:**\n"
        "1. **중요: '마루', '후로링', '나무 바닥', '장판' 관련 문의는 무조건 제외하세요.**\n"
        "2. 오직 **'콘크리트', '도끼다시', '테라조', '에폭시 제거', '면갈이'** 관련 견적 문의만 찾으세요.\n"
        "3. 단순 광고글은 무시하고, 실제 견적 요청이나 업체 추천 글만 골라내세요.\n"
        "결과가 있다면 아래 형식으로 요약해주세요. (없으면 '없음' 출력)\n\n"
        "🚨 **[콘크리트/석재] 견적 문의:**\n"
        "1. **글 제목**\n"
        "   - 📝 **내용:** (핵심 요약)\n"
        "   - 🔗 **링크:** (URL)\n"
    )

    # print(f"-> AI 분석 요청 ({len(candidates)}개)...")
    ai_result = ask_perplexity("콘크리트 전문 영업 비서", prompt_text)
    
    if ai_result and "없음" not in ai_result and len(ai_result) > 20:
        send_telegram(f"📢 [실시간 콘크리트/면갈이 문의]\n\n{ai_result}")

# 30분 타이머
def smart_timer():
    print("⏳ 콘크리트/면갈이 감지기 가동 (30분 간격)")
    while True:
        check_naver_leads_smart()
        time.sleep(1800)

# 수동 정보 검색
def get_info():
    msg = "📋 [공공 입찰 정보]\n\n"
    
    # 1. 나라장터
    msg += "🏛️ [나라장터(G2B) - 폴리싱]\n"
    try:
        end_date = datetime.now().strftime('%Y%m%d0000')
        start_date = (datetime.now() - timedelta(days=90)).strftime('%Y%m%d0000')
        url = 'http://apis.data.go.kr/1230000/BidPublicInfoService/getBidPblancListInfoCnstwk'
        params = { 'serviceKey': SERVICE_KEY, 'numOfRows': '3', 'pageNo': '1', 'inqryDiv': '1', 'bidNtceNm': '폴리싱', 'bidNtceBgnDt': start_date, 'bidNtceEndDt': end_date, 'type': 'json' }
        res = requests.get(url, params=params, timeout=5)
        items = res.json().get('response', {}).get('body', {}).get('items', [])
        if items:
            for i in items: msg += f"• {i.get('bidNtceNm')}\n  🔗 {i.get('bidNtceDtlUrl')}\n"
        else: msg += "• 검색된 공고 없음\n"
    except: msg += "• 접속 실패\n"
    
    # 2. 학교장터 (바로가기만 제공)
    msg += "\n🏫 [학교장터(S2B) 바로가기]\n"
    msg += "🔗 https://www.s2b.kr/ (검색어: 도끼다시, 면갈이, 테라조)\n"

    # 3. 인기통 구인
    msg += "\n🔥 [인기통/카페 구인]\n"
    prompt = "사이트 'inkitong.com'에서 '콘크리트 폴리싱' 구인 글 2개만 찾아줘."
    msg += ask_perplexity("구인 검색", prompt) or "검색 실패"
    
    return msg

def get_economy():
    return ask_perplexity("경제 비서", "한국 부동산/건설 경기 뉴스 3줄 요약.")

def monitor_commands():
    last_id = 0
    send_telegram("🚀 [봇 업데이트] 마루/후로링 제외! 콘크리트/도끼다시/면갈이 집중 모드 시작.")
    while True:
        try:
            res = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates", params={"offset": last_id + 1, "timeout": 20}).json()
            for up in res.get("result", []):
                last_id = up["update_id"]
                text = up.get("message", {}).get("text", "")
                chat_id = up.get("message", {}).get("chat", {}).get("id")
                
                if text == "/?": send_telegram("메뉴: /정보, /경제", chat_id)
                elif text == "/정보": send_telegram(get_info(), chat_id)
                elif text == "/경제": send_telegram(get_economy(), chat_id)
            time.sleep(1)
        except: time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=smart_timer, daemon=True).start()
    monitor_commands()

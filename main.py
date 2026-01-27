import requests
import time
import threading
import json
import re
from datetime import datetime, timedelta

# --- [설정 정보] ---
TOKEN = '8131864943:AAEE77BmAVdTqP06T2JcqIxhTKlCIemc-Ak'
OWNER_ID = '6991113379'
GROUP_ID = '-4663839015' # 단톡방 ID

# 1. 나라장터 키
SERVICE_KEY = 'c2830ec3b623040f9ac01cb9a3980d1c3f6c949e9f4bd765adbfb2432c43b4ed'

# 2. 퍼플렉시티 키 (AI 두뇌)
PPLX_API_KEY = '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'

# 3. ★ 네이버 API 키 (방금 발급받으신 것) ★
NAVER_CLIENT_ID = '7D1q3B5fpC5O4fxVGNmD'
NAVER_CLIENT_SECRET = 'ffJg82MJO2'

# 이미 본 글은 다시 안 보냄 (중복 방지용 메모리)
seen_links = set()

# 텔레그램 전송
def send_telegram(text, target_id=None):
    if target_id is None: target_id = GROUP_ID
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
        if response.status_code != 200: return None
        return response.json()['choices'][0]['message']['content']
    except: return None

# --- [네이버 검색 엔진] ---
def search_naver(query):
    # 블로그와 카페 두 군데를 다 뒤집니다.
    results = []
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    
    # 검색 대상: 블로그(blog), 카페(cafearticle)
    for category in ['blog', 'cafearticle']:
        url = f"https://openapi.naver.com/v1/search/{category}.json"
        # sort='date'로 하면 최신순 정렬됨
        params = { "query": query, "display": 5, "start": 1, "sort": "date" }
        try:
            res = requests.get(url, headers=headers, params=params, timeout=5)
            if res.status_code == 200:
                items = res.json().get('items', [])
                for item in items:
                    # 태그 제거 (<b> 등)
                    clean_title = re.sub('<.*?>', '', item['title'])
                    clean_desc = re.sub('<.*?>', '', item['description'])
                    link = item['link']
                    
                    results.append({
                        'title': clean_title,
                        'desc': clean_desc,
                        'link': link,
                        'source': '블로그' if category == 'blog' else '카페'
                    })
        except: pass
    return results

# --- [핵심: 네이버 수집 -> AI 필터링 -> 보고] ---
def check_naver_leads_smart():
    global seen_links
    
    keywords = [
        "콘크리트 폴리싱 견적", "바닥 면갈이 업체", "도끼다시 연마 광택", 
        "에폭시 제거후 폴리싱", "테라조 복원 비용", "상가바닥 노출 콘크리트 시공",
        "바닥 샌딩 견적", "콘크리트 연마 비용"
    ]
    
    # 1. 네이버에서 최신글 싹 긁어오기
    raw_leads = []
    for key in keywords:
        items = search_naver(key)
        for item in items:
            # 이미 본 링크면 패스 (중복 차단)
            if item['link'] not in seen_links:
                raw_leads.append(item)
                seen_links.add(item['link']) # 본 목록에 추가

    if not raw_leads:
        print("-> 새로운 글이 없습니다.")
        return

    # 2. AI에게 보낼 데이터 정리 (너무 많으면 최근 10개만)
    candidates = raw_leads[:10]
    
    prompt_text = "다음은 네이버 블로그/카페에서 수집한 콘크리트 바닥 시공 관련 최신 글들입니다.\n\n"
    for i, lead in enumerate(candidates):
        prompt_text += f"{i+1}. [{lead['source']}] 제목: {lead['title']}\n   내용요약: {lead['desc']}\n   링크: {lead['link']}\n\n"
        
    prompt_text += (
        "**지시사항:**\n"
        "위 글들 중에서 **'순수 홍보/광고글'은 모두 무시**하고,\n"
        "**'실제 견적 문의', '가격 질문', '업체 추천 요청', '시공 고민'** 등 고객의 수요가 담긴 글만 골라내세요.\n"
        "만약 그런 글이 있다면 아래 형식으로 요약해 주세요. (없으면 '없음'이라고 답하세요)\n\n"
        "🚨 **발견된 유망 고객:**\n"
        "1. **글 제목**\n"
        "   - 📝 **니즈 요약:** (고객이 무엇을 궁금해하는지 한줄 요약)\n"
        "   - 🔗 **링크:** (URL)\n"
    )

    # 3. AI 판독 시작
    print(f"-> AI에게 {len(candidates)}개의 새 글을 분석 요청합니다...")
    ai_result = ask_perplexity("냉철한 영업 비서", prompt_text)
    
    # 4. 결과가 있고, '없음'이 아니면 텔레그램 발사
    if ai_result and "없음" not in ai_result and len(ai_result) > 20:
        send_telegram(f"📢 [네이버 실시간 잠재고객 감지]\n\n{ai_result}")
    else:
        print("-> AI 분석 결과: 건질 만한 문의가 없습니다.")

# 타이머: 30분마다 실행 (API가 공짜고 빠르니까 더 자주 봐도 됩니다!)
def smart_timer():
    print("⏳ 고성능 감지기 가동 (30분 간격)")
    while True:
        check_naver_leads_smart()
        time.sleep(1800) # 30분 대기

# 기존 정보/경제 기능은 그대로
def get_info():
    msg = "📋 [나라장터 & 인기통 정보]\n\n"
    # 나라장터 로직
    try:
        end_date = datetime.now().strftime('%Y%m%d0000')
        start_date = (datetime.now() - timedelta(days=90)).strftime('%Y%m%d0000')
        url = 'http://apis.data.go.kr/1230000/BidPublicInfoService/getBidPblancListInfoCnstwk'
        params = { 'serviceKey': SERVICE_KEY, 'numOfRows': '5', 'pageNo': '1', 'inqryDiv': '1', 'bidNtceNm': '폴리싱', 'bidNtceBgnDt': start_date, 'bidNtceEndDt': end_date, 'type': 'json' }
        res = requests.get(url, params=params, timeout=10)
        items = res.json().get('response', {}).get('body', {}).get('items', [])
        if items:
            for i in items[:5]: msg += f"• [{i.get('bidNtceDt','')[:10]}] {i.get('bidNtceNm')}\n  🔗 {i.get('bidNtceDtlUrl')}\n"
        else: msg += "• 검색된 공고 없음\n"
    except: msg += "• 나라장터 접속 실패\n"
    
    msg += "\n🔥 [인기통/카페 구인]\n"
    prompt = "사이트 'inkitong.com' 또는 네이버 카페에서 '콘크리트 폴리싱' 구인 글 3개 찾아줘. 도장/생산직 제외."
    msg += ask_perplexity("구인 검색", prompt) or "검색 실패"
    return msg

def get_economy():
    return ask_perplexity("경제 비서", "한국 부동산 뉴스 3개, 미국 주식 뉴스 3개 요약해줘.") or "뉴스 검색 실패"

def monitor_commands():
    last_id = 0
    send_telegram("🚀 [고성능 버전] 봇이 가동되었습니다!\n이제 네이버 API + AI가 30분마다 진짜 견적을 찾아냅니다.")
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
                elif text == "/id": send_telegram(f"ID: {chat_id}", chat_id)
            time.sleep(1)
        except: time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=smart_timer, daemon=True).start()
    monitor_commands()

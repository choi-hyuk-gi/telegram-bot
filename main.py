import requests
import time
import threading
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

# --- [설정 정보] ---
TOKEN = '8131864943:AAEE77BmAVdTqP06T2JcqIxhTKlCIemc-Ak'
OWNER_ID = '6991113379'
GROUP_ID = '-4663839015' 

# 1. 나라장터 키
SERVICE_KEY = 'c2830ec3b623040f9ac01cb9a3980d1c3f6c949e9f4bd765adbfb2432c43b4ed'

# 2. 퍼플렉시티 키
PPLX_API_KEY = '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'

# 3. 네이버 API 키
NAVER_CLIENT_ID = '7D1q3B5fpC5O4fxVGNmD'
NAVER_CLIENT_SECRET = 'ffJg82MJO2'

seen_links = set()
latest_lead_report = "🔍 아직 수집된 견적 문의가 없습니다. (잠시 후 자동 업데이트됨)"

def send_telegram(text, target_id=None):
    if target_id is None: target_id = GROUP_ID
    try:
        requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage", params={"chat_id": target_id, "text": text}, timeout=10)
    except Exception as e:
        print(f"❌ 텔레그램 전송 실패: {e}")

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

# --- [네이버 검색] ---
def search_naver(query):
    results = []
    headers = { "X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET }
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

# --- [30분 자동 감지] ---
def check_naver_leads_smart():
    global seen_links, latest_lead_report
    current_time = datetime.now().strftime('%H:%M')
    print(f"\n[{current_time}] 🔍 30분 정기 점검 시작...")
    
    keywords = ["콘크리트 폴리싱 견적", "바닥 면갈이 업체", "도끼다시 연마", "테라조 복원", "에폭시 제거 비용", "바닥보수공사 견적", "침투성 표면 강화제 시공", "액상 하드너 시공", "바탕면 처리", "학교 바닥 샌딩"]
    raw_leads = []
    new_cnt = 0
    for key in keywords:
        items = search_naver(key)
        for item in items:
            if item['link'] not in seen_links:
                raw_leads.append(item)
                seen_links.add(item['link'])
                new_cnt += 1

    if not raw_leads:
        msg = f"⏰ [정기보고 {current_time}]\n지난 30분간 새로 올라온 글이 없습니다. (정상 작동 중)"
        print("   -> 💤 발견된 새 글 없음.")
        send_telegram(msg)
        return

    print(f"   -> ✨ 새로운 글 {new_cnt}개 발견! AI 정밀 분석 중...")
    candidates = raw_leads[:15]
    prompt_text = "다음은 웹에서 수집한 바닥 공사 관련 글들입니다.\n\n"
    for i, lead in enumerate(candidates):
        prompt_text += f"{i+1}. 제목: {lead['title']}\n   내용: {lead['desc']}\n   링크: {lead['link']}\n\n"
    prompt_text += "**지시사항:** 타일, 장판, 왁스 청소는 제외. '콘크리트', '면갈이', '하드너', '도끼다시' 관련만 요약해줘."

    ai_result = ask_perplexity("콘크리트 전문 영업 비서", prompt_text)
    
    if ai_result and "없음" not in ai_result and len(ai_result) > 20:
        send_telegram(f"📢 [실시간 면갈이/하드너 문의]\n\n{ai_result}")
        timestamp = datetime.now().strftime('%m월 %d일 %H:%M')
        latest_lead_report = f"🗓 **[{timestamp} 기준] 최신 견적 리포트**\n{ai_result}"
    else:
        send_telegram(f"⏰ [정기보고 {current_time}]\n새 글이 {new_cnt}개 있었으나, 유의미한 견적(폴리싱/면갈이)이 아니었습니다.")

def smart_timer():
    print("⏳ 감지기 가동")
    check_naver_leads_smart()
    while True:
        time.sleep(1800)
        check_naver_leads_smart()

# --- [정보 통합 화면 (리스트 15개 요청)] ---
def get_info():
    global latest_lead_report
    msg = "📋 **[종합 정보 브리핑]**\n\n"
    
    # 1. 나라장터 (바닥보수 15개 긁어오기)
    msg += "🏛️ **[나라장터(G2B) - 바닥보수 최근 15개]**\n"
    # 검색어 하나로 통일해서 많이 가져옴
    target_keyword = "바닥보수"
    
    end_date = datetime.now().strftime('%Y%m%d0000')
    start_date = (datetime.now() - timedelta(days=60)).strftime('%Y%m%d0000') # 2달치
    url = 'https://apis.data.go.kr/1230000/BidPublicInfoService/getBidPblancListInfoCnstwk'
    
    params = { 
        'serviceKey': SERVICE_KEY,
        'numOfRows': '15',     # ★ 여기를 15개로 늘림
        'pageNo': '1', 
        'inqryDiv': '1', 
        'bidNtceNm': target_keyword, 
        'bidNtceBgnDt': start_date, 
        'bidNtceEndDt': end_date
    }
    
    try:
        res = requests.get(url, params=params, timeout=15)
        if res.status_code == 200:
            try:
                root = ET.fromstring(res.content)
                items = root.findall('.//item')
                if items:
                    for i, item in enumerate(items):
                        name = item.findtext('bidNtceNm')
                        link = item.findtext('bidNtceDtlUrl')
                        date = item.findtext('bidNtceDt')
                        # 날짜 포맷 예쁘게 (2026-01-28)
                        if date: date = f"({date[4:6]}/{date[6:8]})"
                        else: date = ""
                        
                        msg += f"{i+1}. {name} {date}\n   🔗 {link}\n"
                else:
                    msg += "• 검색된 공고가 없습니다.\n"
            except: msg += "• 데이터 파싱 오류\n"
        else: msg += f"• 서버 오류 ({res.status_code})\n"
    except: msg += "• 접속 실패 (타임아웃)\n"

    # 2. 학교장터
    msg += "\n🏫 **[학교장터(S2B)]**\n"
    msg += "🔗 https://www.s2b.kr/ (검색어: 도끼다시, 면갈이)\n"

    # 3. 인기통
    msg += "\n🔥 **[인기통 구인]**\n"
    prompt = "사이트 'inkitong.com'에서 '면갈이' 또는 '폴리싱' 구인 글 2개를 찾아줘. 없으면 '• 최근 공고 없음' 출력."
    search_result = ask_perplexity("구인 검색", prompt)
    if not search_result: search_result = "• 검색 실패"
    msg += f"{search_result}\n"
    
    # 4. 리포트
    msg += "\n-----------------------\n"
    msg += f"📢 **[실시간 웹 견적 현황]**\n{latest_lead_report}"
    
    return msg

def get_economy():
    real_estate = ask_perplexity("부동산 전문가", "한국 부동산 시장 뉴스 5개 요약.")
    stocks = ask_perplexity("주식 전문가", "미국 주식 시장 동향 5개 요약.")
    return f"🏠 [부동산]\n{real_estate}\n\n📈 [주식]\n{stocks}"

def monitor_commands():
    last_id = 0
    print("🚀 봇 재시동: 나라장터 리스트 15개 확장판")
    send_telegram("🚀 [업데이트 완료] 이제 '/정보'를 누르면 나라장터 '바닥보수' 최근 공고 15개를 한 번에 보여줍니다.")
    
    while True:
        try:
            res = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates", params={"offset": last_id + 1, "timeout": 20}).json()
            for up in res.get("result", []):
                last_id = up["update_id"]
                text = up.get("message", {}).get("text", "")
                chat_id = up.get("message", {}).get("chat", {}).get("id")
                
                if text == "/?": send_telegram("메뉴: /정보, /경제", chat_id)
                elif text == "/정보": 
                    send_telegram("⏳ 최근 15개 공고를 불러옵니다...", chat_id)
                    send_telegram(get_info(), chat_id)
                elif text == "/경제": 
                    send_telegram("🤖 뉴스 수집 중...", chat_id)
                    send_telegram(get_economy(), chat_id)
            time.sleep(1)
        except: time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=smart_timer, daemon=True).start()
    monitor_commands()

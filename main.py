import requests
import time
import threading
import json
import re
from datetime import datetime, timedelta
import urllib.parse

# --- [설정 정보] ---
TOKEN = '8131864943:AAEE77BmAVdTqP06T2JcqIxhTKlCIemc-Ak'
OWNER_ID = '6991113379'
GROUP_ID = '-4663839015' 

# 1. 나라장터 키 (타임아웃 해결을 위해 그대로 둠)
SERVICE_KEY = 'c2830ec3b623040f9ac01cb9a3980d1c3f6c949e9f4bd765adbfb2432c43b4ed'

# 2. 퍼플렉시티 키
PPLX_API_KEY = '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'

# 3. 네이버 API 키
NAVER_CLIENT_ID = '7D1q3B5fpC5O4fxVGNmD'
NAVER_CLIENT_SECRET = 'ffJg82MJO2'

# 이미 본 글은 다시 안 보냄
seen_links = set()

# ★ [NEW] 봇이 찾은 최신 견적을 저장해두는 메모장
latest_lead_report = "🔍 아직 수집된 견적 문의가 없습니다. (잠시 후 자동 업데이트됨)"

# 텔레그램 전송
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
        if response.status_code != 200: 
            print(f"⚠️ AI 오류: {response.text}")
            return None
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        print(f"⚠️ AI 연결 실패: {e}")
        return None

# --- [네이버 검색 엔진] ---
def search_naver(query):
    results = []
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
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

# --- [핵심: 돌 바닥 전용 감시 + 무조건 보고] ---
def check_naver_leads_smart():
    global seen_links, latest_lead_report
    
    current_time = datetime.now().strftime('%H:%M')
    print(f"\n[{current_time}] 🔍 30분 정기 점검 시작...")
    
    keywords = [
        "콘크리트 폴리싱 견적", "바닥 면갈이 업체", "도끼다시 연마 광택", 
        "에폭시 제거후 폴리싱", "테라조 복원 비용", "상가바닥 노출 콘크리트 시공",
        "학교 도끼다시 연마", "학교 테라조 공사", 
        "관공서 바닥 면갈이"
    ]
    
    raw_leads = []
    new_cnt = 0
    for key in keywords:
        items = search_naver(key)
        for item in items:
            if item['link'] not in seen_links:
                raw_leads.append(item)
                seen_links.add(item['link'])
                new_cnt += 1

    # 1. 새로운 글이 아예 없을 때 (무조건 보고)
    if not raw_leads:
        msg = f"⏰ [정기보고 {current_time}]\n지난 30분간 새로 올라온 바닥 시공 관련 글이 없습니다. (정상 작동 중)"
        print("   -> 💤 발견된 새 글 없음. (보고 전송)")
        send_telegram(msg)
        return

    print(f"   -> ✨ 새로운 글 {new_cnt}개 발견! AI 분석 중...")
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
        "🚨 **[콘크리트/석재] 견적 문의 발견:**\n"
        "1. **글 제목**\n"
        "   - 📝 **내용:** (핵심 요약)\n"
        "   - 🔗 **링크:** (URL)\n"
    )

    ai_result = ask_perplexity("콘크리트 전문 영업 비서", prompt_text)
    
    # 2. 유효한 견적이 있을 때
    if ai_result and "없음" not in ai_result and len(ai_result) > 20:
        print("   -> 📢 유효한 견적 발견! 텔레그램 전송.")
        send_telegram(f"📢 [실시간 콘크리트/면갈이 문의]\n\n{ai_result}")
        
        timestamp = datetime.now().strftime('%m월 %d일 %H:%M')
        latest_lead_report = f"🗓 **[{timestamp} 기준] 최신 견적 리포트**\n{ai_result}"
    
    # 3. 새 글은 있는데 광고라서 걸러졌을 때 (무조건 보고)
    else:
        msg = f"⏰ [정기보고 {current_time}]\n새 글이 {new_cnt}개 있었으나, 광고/홍보성 글이라 제외했습니다."
        print("   -> 🗑️ AI 분석 결과: 광고로 판단됨. (보고 전송)")
        send_telegram(msg)

# 30분 타이머
def smart_timer():
    print("⏳ 콘크리트/면갈이 감지기 가동 (30분 간격)")
    check_naver_leads_smart() # 켜자마자 한번 실행
    while True:
        time.sleep(1800) # 1800초 = 30분
        check_naver_leads_smart()

# --- [정보 통합 화면] ---
def get_info():
    global latest_lead_report
    msg = "📋 **[종합 정보 브리핑]**\n\n"
    
    # 1. 나라장터 (타임아웃 20초 적용)
    msg += "🏛️ **[나라장터(G2B) - 폴리싱]**\n"
    try:
        end_date = datetime.now().strftime('%Y%m%d0000')
        start_date = (datetime.now() - timedelta(days=90)).strftime('%Y%m%d0000')
        url = 'https://apis.data.go.kr/1230000/BidPublicInfoService/getBidPblancListInfoCnstwk'
        
        params = { 
            'serviceKey': urllib.parse.unquote(SERVICE_KEY),
            'numOfRows': '3', 
            'pageNo': '1', 
            'inqryDiv': '1', 
            'bidNtceNm': '폴리싱', 
            'bidNtceBgnDt': start_date, 
            'bidNtceEndDt': end_date, 
            'type': 'json' 
        }
        
        res = requests.get(url, params=params, timeout=20)
        
        if res.status_code == 200:
            try:
                items = res.json().get('response', {}).get('body', {}).get('items', [])
                if items:
                    for i in items: msg += f"• {i.get('bidNtceNm')}\n  🔗 {i.get('bidNtceDtlUrl')}\n"
                else: msg += "• 검색된 공고 없음 (최근 3개월)\n"
            except:
                msg += f"• 데이터 파싱 실패\n"
        else:
            msg += f"• 서버 오류 ({res.status_code})\n"
            
    except:
        msg += "• 접속 실패 (시간 초과)\n"
    
    # 2. 학교장터
    msg += "\n🏫 **[학교장터(S2B) 바로가기]**\n"
    msg += "🔗 https://www.s2b.kr/ (검색어: 도끼다시, 면갈이, 테라조)\n"

    # 3. 인기통 구인
    msg += "\n🔥 **[인기통/카페 구인]**\n"
    prompt = (
        "사이트 'inkitong.com'에서 '콘크리트 폴리싱' 구인 글 2개를 찾아줘. "
        "만약 없거나 불확실하면 사족 달지 말고 딱 한 마디만 해: '• 최근 올라온 구인 공고가 없습니다.'"
    )
    search_result = ask_perplexity("구인 검색", prompt)
    if not search_result: search_result = "• 검색 실패"
    msg += f"{search_result}\n"
    
    # 4. 봇이 찾은 최신 웹 견적
    msg += "\n-----------------------\n"
    msg += f"📢 **[실시간 웹 견적 감지 현황]**\n{latest_lead_report}"
    
    return msg

# 경제 뉴스
def get_economy():
    real_estate = ask_perplexity("부동산 전문가", "한국 부동산 시장(매매/전세/정책) 최신 뉴스 5개. '1. 제목: 내용' 형식으로 리스트업 해줘.")
    stocks = ask_perplexity("주식 전문가", "미국 주식 및 해외 선물 최신 동향 5개. '1. 제목: 내용' 형식으로 리스트업 해줘.")
    return f"🏠 [부동산 Top 5]\n{real_estate}\n\n-----------------\n\n📈 [미국주식 Top 5]\n{stocks}"

def monitor_commands():
    last_id = 0
    print("🚀 봇 시스템 시작 (30분마다 무조건 생존신고 보냄)")
    send_telegram("🚀 [봇 업데이트 완료]\n이제 30분마다 검색 결과가 없어도 생존 보고를 보냅니다.")
    
    while True:
        try:
            res = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates", params={"offset": last_id + 1, "timeout": 20}).json()
            for up in res.get("result", []):
                last_id = up["update_id"]
                text = up.get("message", {}).get("text", "")
                chat_id = up.get("message", {}).get("chat", {}).get("id")
                
                print(f"📩 메시지 수신: {text}")

                if text == "/?": send_telegram("메뉴: /정보, /경제", chat_id)
                elif text == "/정보": 
                    send_telegram("⏳ 정보 수집 중입니다... (약 15초)", chat_id)
                    send_telegram(get_info(), chat_id)
                elif text == "/경제": 
                    send_telegram("🤖 뉴스 수집 중...", chat_id)
                    send_telegram(get_economy(), chat_id)
            time.sleep(1)
        except Exception as e: 
            print(f"폴링 에러: {e}")
            time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=smart_timer, daemon=True).start()
    monitor_commands()

import requests
import time
import threading
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import urllib.parse
import urllib3

# SSL 경고 무시 설정 (500 에러 해결을 위한 강제 조치)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- [설정 정보] ---
TOKEN = '8131864943:AAEE77BmAVdTqP06T2JcqIxhTKlCIemc-Ak'
GROUP_ID = '-4663839015' 

# 혁기 님의 최신 키 (22.png 확인됨)
SERVICE_KEY = '0e0a27cc23706c81733d714edd365c9dc23178bb70dc4461f44a8f5e211be277'

PPLX_API_KEY = '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'
NAVER_CLIENT_ID = '7D1q3B5fpC5O4fxVGNmD'
NAVER_CLIENT_SECRET = 'ffJg82MJO2'

# 전역 변수
seen_links = set()
latest_lead_report = "🔍 데이터 수집 대기 중..."

# --- [기본 기능] ---
def send_telegram(text, target_id=None):
    if target_id is None: target_id = GROUP_ID
    try:
        requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage", params={"chat_id": target_id, "text": text}, timeout=10)
    except: pass

def ask_perplexity(system_role, user_prompt):
    url = "https://api.perplexity.ai/chat/completions"
    payload = {"model": "sonar-pro", "messages": [{"role": "system", "content": system_role}, {"role": "user", "content": user_prompt}]}
    headers = {"Authorization": f"Bearer {PPLX_API_KEY}", "Content-Type": "application/json"}
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=60)
        return res.json()['choices'][0]['message']['content']
    except: return None

# --- [나라장터 500 에러 해결 함수] ---
def get_g2b_data(keyword, count=15):
    end_date = datetime.now().strftime('%Y%m%d0000')
    start_date = (datetime.now() - timedelta(days=90)).strftime('%Y%m%d0000') # 3달치 조회
    
    # 1. HTTP로 시도 (HTTPS가 500 에러 날 때 효과적)
    base_url = 'http://apis.data.go.kr/1230000/BidPublicInfoService/getBidPblancListInfoCnstwk'
    encoded_keyword = urllib.parse.quote(keyword)
    
    # type 파라미터 제거 (서버 기본값 사용 유도)
    full_url = (f"{base_url}?serviceKey={SERVICE_KEY}&numOfRows={count}&pageNo=1"
                f"&inqryDiv=1&bidNtceNm={encoded_keyword}&bidNtceBgnDt={start_date}"
                f"&bidNtceEndDt={end_date}")
    
    try:
        # verify=False: SSL 인증서 무시 (접속 성공률 높임)
        res = requests.get(full_url, timeout=30, verify=False)
        
        if res.status_code == 200:
            if "SERVICE_KEY_IS_NOT_REGISTERED" in res.text:
                return ["⏳ 서버가 키를 아직 인식 못했습니다. (저녁 10시 이후 자동 해결 예상)"]
            
            try:
                root = ET.fromstring(res.content)
                items = root.findall('.//item')
                results = []
                for item in items:
                    name = item.findtext('bidNtceNm')
                    link = item.findtext('bidNtceDtlUrl')
                    date = item.findtext('bidNtceDt')
                    d_str = f"({date[4:6]}/{date[6:8]})" if date else ""
                    results.append(f"• {name} {d_str}\n  🔗 {link}")
                return results if results else ["• 조건에 맞는 공고가 없습니다 (키워드: 바닥보수)."]
            except:
                return [f"❌ 데이터 파싱 실패: {res.text[:50]}..."]
        else:
            return [f"❌ 서버 오류 ({res.status_code}) - 잠시 후 다시 시도"]
            
    except Exception as e:
        return [f"❌ 접속 실패: {str(e)}"]

# --- [네이버 검색 - 제한 해제 모드] ---
def search_naver(query):
    results = []
    headers = { "X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET }
    # display=30: 최대한 많이 가져옴
    params = { "query": query, "display": 30, "start": 1, "sort": "date" }
    
    for category in ['blog', 'cafearticle', 'webkr']:
        url = f"https://openapi.naver.com/v1/search/{category}.json"
        try:
            res = requests.get(url, headers=headers, params=params, timeout=5)
            if res.status_code == 200:
                items = res.json().get('items', [])
                for item in items:
                    clean_title = re.sub('<.*?>', '', item['title'])
                    clean_desc = re.sub('<.*?>', '', item['description'])
                    # 하루 전 데이터라도 가져오기 위해 날짜 필터 완화
                    results.append({'title': clean_title, 'desc': clean_desc, 'link': item['link']})
        except: pass
    return results

# --- [보고서 생성] ---
def get_info_report():
    global latest_lead_report
    msg = "📋 **[종합 정보 브리핑]**\n\n"
    
    msg += "🏛️ **[나라장터(G2B) - 바닥보수]**\n"
    g2b_items = get_g2b_data("바닥보수", 15)
    msg += "\n".join(g2b_items) + "\n\n"
    
    msg += "🏫 **[학교장터]**\n🔗 https://www.s2b.kr/\n\n"
    
    msg += "-----------------------\n"
    msg += f"📢 **[웹 감지 현황 (무제한 모드)]**\n{latest_lead_report}"
    return msg

def get_economy_report():
    real_estate = ask_perplexity("부동산 전문가", "한국 부동산 시장 뉴스 5개 요약.")
    stocks = ask_perplexity("주식 전문가", "미국 증시 및 선물 시장 동향 5개 요약.")
    return f"🏠 [부동산]\n{real_estate}\n\n📈 [미국증시]\n{stocks}"

# --- [30분 자동 감지 - 필터 해제] ---
def smart_timer():
    global seen_links, latest_lead_report
    print("⏳ 무제한 감지기 가동...")
    
    # 키워드 대폭 추가
    keywords = [
        "바닥보수", "콘크리트 폴리싱", "바닥 면갈이", 
        "하드너 시공", "에폭시 제거", "주차장 바닥", "공장 바닥 보수", "도끼다시 연마"
    ]
    
    while True:
        current_time = datetime.now().strftime('%H:%M')
        raw_leads = []
        
        # 1. 수집
        for k in keywords:
            items = search_naver(k)
            for item in items:
                if item['link'] not in seen_links:
                    raw_leads.append(item)
                    seen_links.add(item['link'])
        
        # 2. 결과 처리 (AI 필터 대폭 완화)
        if raw_leads:
            # AI에게 "최대한 많이 보여줘"라고 지시
            prompt = (
                f"다음 글들 중에서 '바닥 공사'와 관련된 글은 **조금이라도 관련 있으면 전부** 리스트업 해줘.\n"
                f"광고글이라도 가격이나 시공 정보가 있으면 포함시켜.\n"
                f"최근 24시간 내 글이면 무조건 보여줘.\n"
                f"목록: {raw_leads[:40]}"
            )
            ai_res = ask_perplexity("관대한 비서", prompt)
            
            if ai_res and "없음" not in ai_res:
                send_telegram(f"📢 [광대역 감지 알림]\n{ai_res}")
                latest_lead_report = f"🗓 [{current_time} 기준] 발견:\n{ai_res}"
            else:
                # AI가 없다고 해도, 강제로 상위 3개 보여주기 (빈손 방지)
                fallback_msg = ""
                for i, lead in enumerate(raw_leads[:3]):
                    fallback_msg += f"{i+1}. {lead['title']}\n🔗 {lead['link']}\n"
                
                send_telegram(f"⏰ [정기보고 {current_time}]\n확실한 견적은 없으나, 관련 최신 글은 다음과 같습니다:\n{fallback_msg}")
                latest_lead_report = f"🗓 [{current_time} 기준] 단순 관련 글:\n{fallback_msg}"
        else:
            send_telegram(f"⏰ [정기보고 {current_time}]\n지난 30분간 네이버/웹에 새로 올라온 글이 하나도 없습니다.")
            
        time.sleep(1800)

# --- [메인 실행] ---
def monitor_commands():
    last_id = 0
    print("🚀 플로릭스 봇 (500 에러 해결 모드) 시작")
    send_telegram("🚀 [봇 긴급 패치 완료]\n1. 나라장터 접속 방식을 강제로 변경했습니다. (500 에러 대응)\n2. 웹 감지 필터를 없애고 사소한 글도 다 가져옵니다.")
    
    while True:
        try:
            res = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates", params={"offset": last_id + 1, "timeout": 20}).json()
            for up in res.get("result", []):
                last_id = up["update_id"]
                text = up.get("message", {}).get("text", "")
                chat_id = up.get("message", {}).get("chat", {}).get("id")
                
                if text == "/?": send_telegram("/정보, /경제", chat_id)
                elif text == "/정보": 
                    send_telegram("⏳ 강력하게 데이터를 긁어오는 중...", chat_id)
                    send_telegram(get_info_report(), chat_id)
                elif text == "/경제": 
                    send_telegram("🤖 뉴스 수집 중...", chat_id)
                    send_telegram(get_economy_report(), chat_id)
            time.sleep(1)
        except: time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=smart_timer, daemon=True).start()
    monitor_commands()

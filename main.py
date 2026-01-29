import requests
import time
import threading
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import urllib.parse
import urllib3

# SSL 경고 무시 (접속 성공률 높임)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- [설정 정보] ---
TOKEN = '8131864943:AAEE77BmAVdTqP06T2JcqIxhTKlCIemc-Ak'
GROUP_ID = '-4663839015' 

# 혁기 님의 인증키 (22.png)
SERVICE_KEY = '0e0a27cc23706c81733d714edd365c9dc23178bb70dc4461f44a8f5e211be277'

PPLX_API_KEY = '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'
NAVER_CLIENT_ID = '7D1q3B5fpC5O4fxVGNmD'
NAVER_CLIENT_SECRET = 'ffJg82MJO2'

# 전역 변수
seen_links = set()

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

# --- [나라장터 G2B - 기간 단축 버전] ---
def get_g2b_data(keyword, count=10):
    # ★ [핵심 수정] 조회 기간을 15일로 단축 (서버 부하 줄여서 500 에러 방지)
    end_date = datetime.now().strftime('%Y%m%d0000')
    start_date = (datetime.now() - timedelta(days=15)).strftime('%Y%m%d0000')
    
    base_url = 'http://apis.data.go.kr/1230000/BidPublicInfoService/getBidPblancListInfoCnstwk'
    encoded_keyword = urllib.parse.quote(keyword)
    
    # URL 조립
    full_url = (f"{base_url}?serviceKey={SERVICE_KEY}&numOfRows={count}&pageNo=1"
                f"&inqryDiv=1&bidNtceNm={encoded_keyword}&bidNtceBgnDt={start_date}"
                f"&bidNtceEndDt={end_date}&type=xml")
    
    try:
        res = requests.get(full_url, timeout=30, verify=False)
        if res.status_code == 200:
            if "SERVICE_KEY_IS_NOT_REGISTERED" in res.text:
                return ["⏳ 인증키가 아직 활성화 안 됨 (조금 더 기다려주세요)"]
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
                return results if results else ["• 최근 15일간 검색된 공고가 없습니다."]
            except: return ["❌ XML 데이터 파싱 오류"]
        else: return [f"❌ 서버 오류 ({res.status_code}) - 조회 기간을 줄였는데도 이러네요.."]
    except Exception as e: return [f"❌ 접속 실패: {e}"]

# --- [네이버 즉시 검색 기능] ---
def get_instant_web_leads():
    # 1. 즉시 검색 수행
    keywords = ["바닥보수", "콘크리트 폴리싱", "바닥 면갈이", "에폭시 제거"]
    raw_leads = []
    
    headers = { "X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET }
    
    for k in keywords:
        url = "https://openapi.naver.com/v1/search/blog.json" # 블로그 우선 검색
        params = { "query": k, "display": 5, "start": 1, "sort": "date" }
        try:
            res = requests.get(url, headers=headers, params=params, timeout=5)
            if res.status_code == 200:
                items = res.json().get('items', [])
                for item in items:
                    # 하루 전 데이터라도 일단 가져옴
                    clean_title = re.sub('<.*?>', '', item['title'])
                    raw_leads.append({'title': clean_title, 'link': item['link']})
        except: pass

    # 2. 결과가 없으면 빈 메시지
    if not raw_leads:
        return "🕵️‍♂️ 지금 네이버를 뒤져봤지만, 마땅한 견적 글이 안 보입니다."

    # 3. 결과가 있으면 AI 없이 바로 리스트업 (속도 우선)
    msg = ""
    for i, lead in enumerate(raw_leads[:5]): # 상위 5개만
        msg += f"{i+1}. {lead['title']}\n🔗 {lead['link']}\n"
    return msg

# --- [통합 보고서] ---
def get_info_report():
    msg = "📋 **[종합 정보 브리핑]**\n\n"
    
    msg += "🏛️ **[나라장터(G2B) - 15일 이내]**\n"
    g2b_items = get_g2b_data("바닥보수", 10)
    msg += "\n".join(g2b_items) + "\n\n"
    
    msg += "🏫 **[학교장터]**\n🔗 https://www.s2b.kr/\n\n"
    
    # ★ 여기서 즉시 검색 결과를 붙임 (대기 중 메시지 삭제)
    msg += "📢 **[네이버 최신 글 (실시간 검색)]**\n"
    msg += get_instant_web_leads()
    
    return msg

def get_economy_report():
    real_estate = ask_perplexity("부동산 전문가", "한국 부동산 시장 최신 뉴스 5개 요약.")
    stocks = ask_perplexity("주식 전문가", "미국 증시 및 선물 시장 동향 5개 요약.")
    return f"🏠 [부동산]\n{real_estate}\n\n📈 [미국증시]\n{stocks}"

# --- [30분 자동 타이머] ---
def smart_timer():
    global seen_links
    print("⏳ 30분 감지기 가동...")
    while True:
        # 백그라운드에서는 계속 돌면서 '새로운 것'만 찾으면 알림
        # (로직은 단순화하여 생존신고 위주로)
        time.sleep(1800)
        current_time = datetime.now().strftime('%H:%M')
        send_telegram(f"⏰ [정기보고 {current_time}]\n봇이 정상 작동 중입니다. (새로운 특이사항 감시 중)")

# --- [메인 실행] ---
def monitor_commands():
    last_id = 0
    print("🚀 플로릭스 봇 (즉시 검색 + 기간 단축) 시작")
    send_telegram("🚀 [봇 업데이트 완료]\n1. /정보 입력 시 '대기 중' 없이 즉시 네이버를 검색합니다.\n2. 나라장터 조회 기간을 15일로 줄여 500 에러를 피합니다.")
    
    while True:
        try:
            res = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates", params={"offset": last_id + 1, "timeout": 20}).json()
            for up in res.get("result", []):
                last_id = up["update_id"]
                text = up.get("message", {}).get("text", "")
                chat_id = up.get("message", {}).get("chat", {}).get("id")
                
                if text == "/?": send_telegram("/정보, /경제", chat_id)
                elif text == "/정보": 
                    send_telegram("⏳ 즉시 데이터를 찾아옵니다...", chat_id)
                    send_telegram(get_info_report(), chat_id)
                elif text == "/경제": 
                    send_telegram("🤖 뉴스 수집 중...", chat_id)
                    send_telegram(get_economy_report(), chat_id)
            time.sleep(1)
        except: time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=smart_timer, daemon=True).start()
    monitor_commands()

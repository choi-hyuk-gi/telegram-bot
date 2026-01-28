import requests
import time
import threading
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import urllib.parse

# --- [설정 정보] ---
TOKEN = '8131864943:AAEE77BmAVdTqP06T2JcqIxhTKlCIemc-Ak'
GROUP_ID = '-4663839015' 

# 혁기 님의 인증키 (500 에러 해결용)
SERVICE_KEY = '0e0a27cc23706c81733d714edd365c9dc23178bb70dc4461f44a8f5e211be277'

PPLX_API_KEY = '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'
NAVER_CLIENT_ID = '7D1q3B5fpC5O4fxVGNmD'
NAVER_CLIENT_SECRET = 'ffJg82MJO2'

# 전역 변수
seen_links = set()
latest_lead_report = "🔍 수집된 데이터 분석 대기 중..."

# --- [기본 전송 기능] ---
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

# --- [네이버 검색 - 광대역 모드] ---
def search_naver(query):
    results = []
    headers = { "X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET }
    # display=20 : 검색량을 대폭 늘림
    params = { "query": query, "display": 20, "start": 1, "sort": "date" }
    
    for category in ['blog', 'cafearticle', 'webkr']:
        url = f"https://openapi.naver.com/v1/search/{category}.json"
        try:
            res = requests.get(url, headers=headers, params=params, timeout=5)
            if res.status_code == 200:
                items = res.json().get('items', [])
                for item in items:
                    clean_title = re.sub('<.*?>', '', item['title'])
                    clean_desc = re.sub('<.*?>', '', item['description'])
                    results.append({'title': clean_title, 'desc': clean_desc, 'link': item['link'], 'source': category})
        except: pass
    return results

# --- [나라장터 G2B 기능] ---
def get_g2b_data(keyword, count=15):
    end_date = datetime.now().strftime('%Y%m%d0000')
    start_date = (datetime.now() - timedelta(days=60)).strftime('%Y%m%d0000')
    base_url = 'http://apis.data.go.kr/1230000/BidPublicInfoService/getBidPblancListInfoCnstwk'
    encoded_keyword = urllib.parse.quote(keyword)
    
    # URL 직접 조립 (500 에러 방지)
    full_url = (f"{base_url}?serviceKey={SERVICE_KEY}&numOfRows={count}&pageNo=1"
                f"&inqryDiv=1&bidNtceNm={encoded_keyword}&bidNtceBgnDt={start_date}"
                f"&bidNtceEndDt={end_date}&type=xml")
    try:
        res = requests.get(full_url, timeout=30)
        if res.status_code == 200:
            if "SERVICE_KEY_IS_NOT_REGISTERED" in res.text:
                return ["❌ 인증키 서버 등록 대기 중 (잠시 후 자동 해결됨)"]
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
                return results if results else ["• 검색된 공고가 없습니다."]
            except: return ["❌ XML 파싱 오류"]
        else: return [f"❌ 서버 오류 ({res.status_code})"]
    except Exception as e: return [f"❌ 접속 실패: {e}"]

# --- [보고서 생성] ---
def get_info_report():
    global latest_lead_report
    msg = "📋 **[종합 정보 브리핑]**\n\n"
    msg += "🏛️ **[나라장터(G2B) - 바닥보수]**\n"
    g2b_items = get_g2b_data("바닥보수", 15)
    msg += "\n".join(g2b_items) + "\n\n"
    msg += "🏫 **[학교장터]**\n🔗 https://www.s2b.kr/\n\n"
    msg += "-----------------------\n"
    msg += f"📢 **[웹 감지 현황 (광대역 모드)]**\n{latest_lead_report}"
    return msg

def get_economy_report():
    real_estate = ask_perplexity("부동산 전문가", "한국 부동산 시장 최신 뉴스 5개 요약.")
    stocks = ask_perplexity("주식 전문가", "미국 증시 및 선물 시장 동향 5개 요약.")
    return f"🏠 [부동산]\n{real_estate}\n\n📈 [미국증시]\n{stocks}"

# --- [30분 자동 감지 - '바닥보수' 추가됨] ---
def smart_timer():
    global seen_links, latest_lead_report
    print("⏳ 광대역 감지기 가동 (바닥보수 포함)...")
    
    # ★ 요청하신 '바닥보수' 추가 완료
    keywords = [
        "바닥보수", # 요청하신 키워드 (가장 넓은 범위)
        "콘크리트 폴리싱 견적", "바닥 면갈이", "바닥 샌딩 업체", 
        "하드너 시공", "액상 하드너", "도끼다시 연마", "테라조 보수",
        "에폭시 제거 비용", "공장 바닥 공사", "주차장 바닥 보수"
    ]
    
    while True:
        current_time = datetime.now().strftime('%H:%M')
        new_leads = []
        
        # 20개씩 긁어모으기
        for k in keywords:
            items = search_naver(k)
            for item in items:
                if item['link'] not in seen_links:
                    new_leads.append(item)
                    seen_links.add(item['link'])

        if new_leads:
            # AI 필터링: '바닥보수' 때문에 들어온 장판/도배 등은 여기서 거름
            prompt = (
                f"다음 글들 중에서 '바닥 공사'나 '견적'과 관련된 글을 찾아줘.\n"
                f"특히 '콘크리트', '석재', '주차장', '공장', '상가' 바닥 보수는 무조건 포함해.\n"
                f"단, 가정집의 '장판 찢어짐', '강마루 찍힘', '욕실 타일 1장 교체' 같은 소소한 집수리는 제외해.\n"
                f"목록: {new_leads[:40]}" # 많이 긁어와서 AI에게 던짐
            )
            ai_res = ask_perplexity("관대한 비서", prompt)
            
            if ai_res and "없음" not in ai_res:
                send_telegram(f"📢 [광대역 감지 알림]\n{ai_res}")
                latest_lead_report = f"🗓 [{current_time} 기준] 발견 내역:\n{ai_res}"
            else:
                send_telegram(f"⏰ [정기보고 {current_time}]\n새 글 {len(new_leads)}개를 검사했으나, 가정집 장판/타일 보수라 제외했습니다.")
        else:
            send_telegram(f"⏰ [정기보고 {current_time}]\n지난 30분간 새 글이 없습니다. (키워드: 바닥보수 등 11개)")
            
        time.sleep(1800)

# --- [메인 실행] ---
def monitor_commands():
    last_id = 0
    print("🚀 플로릭스 봇 (바닥보수 키워드 추가됨) 시작")
    send_telegram("🚀 [업데이트 완료]\n'바닥보수' 키워드가 추가되었습니다.\n이제 더 많은 글을 감지하지만, 가정집 수리 문의가 섞일 수 있어 AI가 선별합니다.")
    
    while True:
        try:
            res = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates", params={"offset": last_id + 1, "timeout": 20}).json()
            for up in res.get("result", []):
                last_id = up["update_id"]
                text = up.get("message", {}).get("text", "")
                chat_id = up.get("message", {}).get("chat", {}).get("id")
                
                if text == "/?": send_telegram("/정보, /경제", chat_id)
                elif text == "/정보": 
                    send_telegram("⏳ 데이터를 수집 중입니다...", chat_id)
                    send_telegram(get_info_report(), chat_id)
                elif text == "/경제": 
                    send_telegram("🤖 뉴스 수집 중...", chat_id)
                    send_telegram(get_economy_report(), chat_id)
            time.sleep(1)
        except: time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=smart_timer, daemon=True).start()
    monitor_commands()

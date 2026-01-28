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

# ★ 혁기 님이 새로 발급받으신 최신 인증키
SERVICE_KEY = '0e0a27cc23706c81733d714edd365c9dc23178bb70dc4461f44a8f5e211be277'

PPLX_API_KEY = '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'
NAVER_CLIENT_ID = '7D1q3B5fpC5O4fxVGNmD'
NAVER_CLIENT_SECRET = 'ffJg82MJO2'

# 전역 변수
seen_links = set()
latest_lead_report = "🔍 아직 수집된 견적 문의가 없습니다. (잠시 후 자동 업데이트됨)"

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
                    results.append({'title': clean_title, 'desc': clean_desc, 'link': item['link'], 'source': category})
        except: pass
    return results

# --- [나라장터 데이터] ---

def get_g2b_data(keyword, count=15):
    end_date = datetime.now().strftime('%Y%m%d0000')
    start_date = (datetime.now() - timedelta(days=60)).strftime('%Y%m%d0000')
    base_url = 'http://apis.data.go.kr/1230000/BidPublicInfoService/getBidPblancListInfoCnstwk'
    encoded_keyword = urllib.parse.quote(keyword)
    
    # 서버 오류 방지를 위한 URL 직접 조립
    full_url = (f"{base_url}?serviceKey={SERVICE_KEY}&numOfRows={count}&pageNo=1"
                f"&inqryDiv=1&bidNtceNm={encoded_keyword}&bidNtceBgnDt={start_date}"
                f"&bidNtceEndDt={end_date}&type=xml")
    
    try:
        res = requests.get(full_url, timeout=20)
        if res.status_code == 200:
            if "SERVICE_KEY_IS_NOT_REGISTERED" in res.text:
                return "❌ 오류: 새 인증키가 아직 활성화되지 않았습니다. (1~2시간 대기 필요)"
            
            root = ET.fromstring(res.content)
            items = root.findall('.//item')
            results = []
            for item in items:
                name = item.findtext('bidNtceNm')
                link = item.findtext('bidNtceDtlUrl')
                date = item.findtext('bidNtceDt')
                results.append(f"• {name} ({date[4:6]}/{date[6:8]})\n  🔗 {link}")
            return results if results else ["• 최근 공고 없음"]
        return f"❌ 서버 오류 ({res.status_code})"
    except Exception as e:
        return f"❌ 접속 실패: {e}"

# --- [보고서 및 경제 뉴스] ---

def get_info_report():
    global latest_lead_report
    msg = "📋 **[종합 정보 브리핑]**\n\n🏛️ **[나라장터(G2B) - 바닥보수 최근 15개]**\n"
    g2b_items = get_g2b_data("바닥보수", 15)
    
    if isinstance(g2b_items, list):
        msg += "\n".join(g2b_items)
    else:
        msg += g2b_items

    msg += "\n\n🏫 **[학교장터(S2B)]**\n🔗 https://www.s2b.kr/\n"
    msg += f"\n📢 **[실시간 웹 견적 현황]**\n{latest_lead_report}"
    return msg

def get_economy_report():
    real_estate = ask_perplexity("부동산 전문가", "한국 부동산 시장 최신 뉴스 5개 요약.")
    stocks = ask_perplexity("주식 전문가", "미국 주식 및 선물 시장 동향 5개 요약.")
    return f"🏠 [부동산 뉴스]\n{real_estate}\n\n📈 [증시 뉴스]\n{stocks}"

# --- [30분 자동 타이머] ---

def smart_timer():
    global seen_links, latest_lead_report
    while True:
        current_time = datetime.now().strftime('%H:%M')
        print(f"[{current_time}] 정기 점검 시작...")
        
        keywords = ["콘크리트 폴리싱 견적", "바닥 면갈이 업체", "하드너 시공"]
        new_leads = []
        for k in keywords:
            items = search_naver(k)
            for item in items:
                if item['link'] not in seen_links:
                    new_leads.append(item)
                    seen_links.add(item['link'])

        if new_leads:
            prompt = f"다음 글 중 실제 폴리싱/면갈이 견적 문의만 요약: {new_leads}"
            ai_res = ask_perplexity("비서", prompt)
            if ai_res and "없음" not in ai_res:
                send_telegram(f"📢 [신규 견적 발견]\n{ai_res}")
                latest_lead_report = f"🗓 [{current_time} 기준]\n{ai_res}"
            else:
                send_telegram(f"⏰ [정기보고 {current_time}] 새 글은 있었으나 광고였습니다.")
        else:
            send_telegram(f"⏰ [정기보고 {current_time}] 새로 올라온 시공 문의가 없습니다. (정상 작동 중)")
            
        time.sleep(1800) # 30분 대기

# --- [명령어 모니터링] ---

def monitor_commands():
    last_id = 0
    print("🚀 플로릭스 봇 모든 기능 복구 완료")
    send_telegram("🚀 [업데이트 완료]\n1. /정보 (나라장터 15개 리스트)\n2. /경제 (부동산/증시 뉴스)\n3. 30분 정기 생존 보고 기능 복구")
    
    while True:
        try:
            res = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates", params={"offset": last_id + 1, "timeout": 20}).json()
            for up in res.get("result", []):
                last_id = up["update_id"]
                text = up.get("message", {}).get("text", "")
                chat_id = up.get("message", {}).get("chat", {}).get("id")
                
                if text == "/정보":
                    send_telegram("⏳ 데이터를 수집 중입니다...", chat_id)
                    send_telegram(get_info_report(), chat_id)
                elif text == "/경제":
                    send_telegram("🤖 최신 경제 뉴스를 요약 중입니다...", chat_id)
                    send_telegram(get_economy_report(), chat_id)
            time.sleep(1)
        except: time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=smart_timer, daemon=True).start()
    monitor_commands()

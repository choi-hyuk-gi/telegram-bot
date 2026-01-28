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

# ★ 혁기 님이 재발급받으신 최신 키
SERVICE_KEY = '0e0a27cc23706c81733d714edd365c9dc23178bb70dc4461f44a8f5e211be277'

PPLX_API_KEY = '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'
NAVER_CLIENT_ID = '7D1q3B5fpC5O4fxVGNmD'
NAVER_CLIENT_SECRET = 'ffJg82MJO2'

# 전역 변수
seen_links = set()
latest_lead_report = "🔍 아직 수집된 견적 문의가 없습니다. (잠시 후 자동 업데이트됨)"

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

# --- [나라장터 G2B 기능 (500 에러 방지)] ---
def get_g2b_data(keyword, count=15):
    """
    나라장터에서 데이터를 가져옵니다. 
    URL에 키를 직접 넣어 인코딩 오류를 방지합니다.
    """
    end_date = datetime.now().strftime('%Y%m%d0000')
    start_date = (datetime.now() - timedelta(days=60)).strftime('%Y%m%d0000')
    
    base_url = 'http://apis.data.go.kr/1230000/BidPublicInfoService/getBidPblancListInfoCnstwk'
    encoded_keyword = urllib.parse.quote(keyword)
    
    # ★ 핵심: requests params를 쓰지 않고 URL을 직접 조립 (500 에러 해결책)
    full_url = (f"{base_url}?serviceKey={SERVICE_KEY}&numOfRows={count}&pageNo=1"
                f"&inqryDiv=1&bidNtceNm={encoded_keyword}&bidNtceBgnDt={start_date}"
                f"&bidNtceEndDt={end_date}&type=xml")
    
    try:
        # verify=False로 SSL 인증서 문제 무시
        res = requests.get(full_url, timeout=30)
        
        if res.status_code == 200:
            if "SERVICE_KEY_IS_NOT_REGISTERED" in res.text:
                return ["❌ 오류: 새 인증키가 아직 조달청 서버에 등록되지 않았습니다. (약 1시간 대기 필요)"]
            
            try:
                root = ET.fromstring(res.content)
                items = root.findall('.//item')
                results = []
                for item in items:
                    name = item.findtext('bidNtceNm')
                    link = item.findtext('bidNtceDtlUrl')
                    date = item.findtext('bidNtceDt')
                    date_fmt = f"({date[4:6]}/{date[6:8]})" if date else ""
                    results.append(f"• {name} {date_fmt}\n  🔗 {link}")
                return results if results else ["• 검색된 공고가 없습니다."]
            except:
                return ["❌ 데이터 형식 오류 (XML 파싱 실패)"]
        else:
            return [f"❌ 서버 오류 ({res.status_code}) - 잠시 후 다시 시도하세요."]
    except Exception as e:
        return [f"❌ 접속 실패: {e}"]

# --- [보고서 생성 기능] ---
def get_info_report():
    global latest_lead_report
    msg = "📋 **[종합 정보 브리핑]**\n\n"
    
    # 1. 나라장터 바닥보수 리스트 (15개)
    msg += "🏛️ **[나라장터(G2B) - 바닥보수 최근 15개]**\n"
    g2b_items = get_g2b_data("바닥보수", 15)
    msg += "\n".join(g2b_items) + "\n"

    # 2. 학교장터 링크
    msg += "\n🏫 **[학교장터(S2B)]**\n🔗 https://www.s2b.kr/ (추천: 면갈이, 테라조)\n"
    
    # 3. 30분간 감지된 웹 견적 내역
    msg += "\n-----------------------\n"
    msg += f"📢 **[실시간 웹 견적 감지 현황]**\n{latest_lead_report}"
    
    return msg

# --- [경제 뉴스 기능 (복구됨)] ---
def get_economy_report():
    real_estate = ask_perplexity("부동산 전문가", "한국 부동산 시장(매매/전세/정책) 최신 뉴스 5개 요약해줘.")
    stocks = ask_perplexity("주식 전문가", "미국 주식 시장 및 해외선물 최신 동향 5개 요약해줘.")
    return f"🏠 [부동산 뉴스]\n{real_estate}\n\n📈 [미국증시 & 선물]\n{stocks}"

# --- [30분 자동 감지 타이머] ---
def smart_timer():
    global seen_links, latest_lead_report
    print("⏳ 30분 감지기 시작...")
    
    while True:
        current_time = datetime.now().strftime('%H:%M')
        
        # 1. 네이버 검색 (키워드: 폴리싱, 면갈이, 하드너)
        keywords = ["콘크리트 폴리싱 견적", "바닥 면갈이 업체", "하드너 시공 비용"]
        new_leads = []
        for k in keywords:
            items = search_naver(k)
            for item in items:
                if item['link'] not in seen_links:
                    new_leads.append(item)
                    seen_links.add(item['link'])

        # 2. 결과 분석 및 보고
        if new_leads:
            prompt = f"다음 글들 중에서 광고 말고 진짜 '견적 문의'나 '업체 찾는 글'만 골라줘: {new_leads}"
            ai_res = ask_perplexity("비서", prompt)
            
            if ai_res and "없음" not in ai_res:
                send_telegram(f"📢 [신규 견적 발견!]\n{ai_res}")
                latest_lead_report = f"🗓 [{current_time} 기준] 신규 발견:\n{ai_res}"
            else:
                # 새 글은 있었지만 광고였을 때
                send_telegram(f"⏰ [정기보고 {current_time}]\n새 글이 감지되었으나, 광고성 글이라 제외했습니다.")
        else:
            # 새 글이 하나도 없을 때 (생존 신고)
            send_telegram(f"⏰ [정기보고 {current_time}]\n지난 30분간 새로 올라온 견적 문의가 없습니다. (정상 작동 중)")
            
        time.sleep(1800) # 30분 대기

# --- [메인 실행부] ---
def monitor_commands():
    last_id = 0
    print("🚀 플로릭스 봇 재가동 (경제기능+정기보고+G2B수정)")
    send_telegram("🚀 [봇 시스템 복구 완료]\n1. /경제 기능이 돌아왔습니다.\n2. 30분마다 꼬박꼬박 보고합니다.\n3. 새 인증키로 나라장터 접속을 시도합니다.")
    
    while True:
        try:
            res = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates", params={"offset": last_id + 1, "timeout": 20}).json()
            for up in res.get("result", []):
                last_id = up["update_id"]
                text = up.get("message", {}).get("text", "")
                chat_id = up.get("message", {}).get("chat", {}).get("id")
                
                if text == "/?":
                    send_telegram("메뉴:\n/정보 : 나라장터 & 웹 견적 브리핑\n/경제 : 부동산 & 증시 뉴스", chat_id)
                elif text == "/정보":
                    send_telegram("⏳ 나라장터(바닥보수 15개) 및 웹 데이터를 긁어오는 중...", chat_id)
                    send_telegram(get_info_report(), chat_id)
                elif text == "/경제":
                    send_telegram("🤖 최신 경제 뉴스를 요약 중입니다...", chat_id)
                    send_telegram(get_economy_report(), chat_id)
                    
            time.sleep(1)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=smart_timer, daemon=True).start()
    monitor_commands()

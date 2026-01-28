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

# ★ 혁기 님이 방금 재발급받으신 새 키입니다.
# 만약 실행 시 '인증키 미등록' 에러가 나면 [인증키 복사] 버튼을 눌러 
# 'Encoding'이라고 적힌 키를 여기 다시 넣어보세요.
SERVICE_KEY = '0e0a27cc23706c81733d714edd365c9dc23178bb70dc4461f44a8f5e211be277'

PPLX_API_KEY = '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'
NAVER_CLIENT_ID = '7D1q3B5fpC5O4fxVGNmD'
NAVER_CLIENT_SECRET = 'ffJg82MJO2'

seen_links = set()
latest_lead_report = "🔍 아직 수집된 견적 문의가 없습니다. (잠시 후 자동 업데이트됨)"

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

# --- [나라장터 15개 리스트 가져오기] ---
def get_g2b_data(keyword, count=15):
    end_date = datetime.now().strftime('%Y%m%d0000')
    start_date = (datetime.now() - timedelta(days=60)).strftime('%Y%m%d0000')
    
    base_url = 'http://apis.data.go.kr/1230000/BidPublicInfoService/getBidPblancListInfoCnstwk'
    encoded_keyword = urllib.parse.quote(keyword)
    
    # 500 에러 방지를 위해 URL 직접 조립
    full_url = (f"{base_url}?serviceKey={SERVICE_KEY}&numOfRows={count}&pageNo=1"
                f"&inqryDiv=1&bidNtceNm={encoded_keyword}&bidNtceBgnDt={start_date}"
                f"&bidNtceEndDt={end_date}&type=xml")
    
    try:
        res = requests.get(full_url, timeout=20)
        if res.status_code == 200:
            if "SERVICE_KEY_IS_NOT_REGISTERED" in res.text:
                return "❌ 오류: 새 인증키가 아직 활성화되지 않았습니다. (1시간 후 재시도 권장)"
            
            root = ET.fromstring(res.content)
            items = root.findall('.//item')
            results = []
            for item in items:
                name = item.findtext('bidNtceNm')
                link = item.findtext('bidNtceDtlUrl')
                date = item.findtext('bidNtceDt')
                results.append(f"• {name} ({date[4:6]}/{date[6:8]})\n  🔗 {link}")
            return results if results else ["• 검색 결과가 없습니다."]
        return f"❌ 서버 오류 ({res.status_code})"
    except Exception as e:
        return f"❌ 접속 실패: {e}"

def get_info_report():
    global latest_lead_report
    msg = "📋 **[종합 정보 브리핑]**\n\n🏛️ **[나라장터(G2B) - 바닥보수 최근 15개]**\n"
    g2b_items = get_g2b_data("바닥보수", 15)
    
    if isinstance(g2b_items, list):
        msg += "\n".join(g2b_items)
    else:
        msg += g2b_items

    msg += "\n\n🏫 **[학교장터(S2B)]**\n🔗 https://www.s2b.kr/\n"
    msg += f"\n📢 **[실시간 웹 견적 감지 현황]**\n{latest_lead_report}"
    return msg

def monitor_commands():
    last_id = 0
    print("🚀 플로릭스 봇 가동 (새 인증키 적용됨)")
    send_telegram("🚀 [봇 업데이트 완료]\n새로 발급받으신 인증키로 접속을 시도합니다.")
    
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
            time.sleep(1)
        except: time.sleep(5)

if __name__ == "__main__":
    monitor_commands()

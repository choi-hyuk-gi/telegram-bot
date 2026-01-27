import requests
from bs4 import BeautifulSoup
import time
import threading
import random
import json
from datetime import datetime, timedelta

# --- [설정 정보] ---
TOKEN = '8131864943:AAEE77BmAVdTqP06T2JcqIxhTKlCIemc-Ak'
CHAT_ID = '6991113379'

# 1. 나라장터 키 (공사 조회용)
SERVICE_KEY = 'c2830ec3b623040f9ac01cb9a3980d1c3f6c949e9f4bd765adbfb2432c43b4ed'

# 2. 퍼플렉시티 키 (혹시 새로 받으셨으면 이걸 바꿔주세요!)
PPLX_API_KEY = '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'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

seen_instagram = set()

# --- [AI 기능: 정밀 진단 모드] ---
def ask_perplexity(system_role, user_prompt):
    url = "https://api.perplexity.ai/chat/completions"
    
    payload = {
        "model": "llama-3.1-sonar-large-128k-online", 
        "messages": [
            { "role": "system", "content": system_role },
            { "role": "user", "content": user_prompt }
        ]
    }
    
    headers = {
        "Authorization": f"Bearer {PPLX_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        
        # ★ 여기가 핵심: 에러가 나면 "왜 안 되는지" 내용을 그대로 보여줌 ★
        if response.status_code != 200:
            return f"🚨 [AI 거절] 이유: {response.text}"
            
        result = response.json()
        return result['choices'][0]['message']['content']
    except Exception as e:
        return f"⚠️ [시스템 에러]: {str(e)}"

# 1. 나라장터 (공사) + 인기통 (AI)
def get_info():
    msg = "📋 [나라장터 & 인기통 정보]\n\n"
    
    # (1) 나라장터
    msg += "🏛️ [나라장터 공사 공고]\n"
    try:
        end_date = datetime.now().strftime('%Y%m%d0000')
        start_date = (datetime.now() - timedelta(days=180)).strftime('%Y%m%d0000')
        url = 'http://apis.data.go.kr/1230000/BidPublicInfoService/getBidPblancListInfoCnstwk'
        
        params = {
            'serviceKey': SERVICE_KEY,
            'numOfRows': '5',
            'pageNo': '1',
            'inqryDiv': '1',
            'bidNtceNm': '폴리싱',
            'bidNtceBgnDt': start_date,
            'bidNtceEndDt': end_date,
            'type': 'json'
        }
        
        res = requests.get(url, params=params, timeout=30)
        if res.status_code == 200:
            data = res.json()
            items = data.get('response', {}).get('body', {}).get('items', [])
            if items:
                for i in items[:5]:
                    title = i.get('bidNtceNm', '제목없음')
                    link = i.get('bidNtceDtlUrl', '#')
                    date = i.get('bidNtceDt', '')[:10]
                    msg += f"• [{date}] {title}\n   🔗 {link}\n"
            else:
                msg += "• 검색된 공고가 없습니다.\n"
        else:
            msg += f"• 정부 서버 점검 중 (코드: {res.status_code})\n  (아침 9시 이후 정상화됩니다)"
    except Exception as e:
        msg += f"• 접속 오류 (정부 서버 불안정)\n"

    msg += "\n--------------------------------\n\n"

    # (2) 인기통 (AI 검색)
    msg += "🔥 [인기통 폴리싱 관련 글 (AI)]\n"
    inkitong_result = ask_perplexity(
        "당신은 구인구직 정보 검색 비서입니다.",
        "웹사이트 '인기통(inkitong.com)' 또는 한국 건설 관련 커뮤니티에서 '폴리싱' 또는 '바닥 시공' 관련 최신 게시글이나 구인 정보를 3~5개 찾아줘.\n반드시 '글 제목'과 '해당 글의 링크(URL)'를 함께 리스트 형식으로 출력해줘."
    )
    msg += inkitong_result
    
    return msg

# 2. 경제 뉴스 (AI 브리핑)
def get_economy():
    send_telegram("🤖 AI가 상태를 정밀 진단 중입니다... (에러 메시지 확인용)")
    
    real_estate = ask_perplexity(
        "당신은 부동산 전문가입니다.",
        "지금 한국 부동산 시장(매매, 전세, 정책) 관련 가장 중요한 최신 뉴스 5개를 선정해서, 각 뉴스마다 핵심 내용을 2줄로 요약해줘."
    )
    stocks = ask_perplexity(
        "당신은 주식 전문가입니다.",
        "미국 주식 시장 및 해외 선물 최신 동향 뉴스 5개를 선정해서, 각 뉴스마다 핵심 내용을 2줄로 요약해줘."
    )
    
    msg = f"🏠 [부동산 주요사항 5선]\n{real_estate}\n\n"
    msg += f"--------------------------------\n\n"
    msg += f"📈 [미국주식 & 해외선물 5선]\n{stocks}"
    
    return msg

# 3. 인스타그램 (유지)
def check_instagram():
    global seen_instagram
    url = "https://imginn.org/tags/콘크리트폴리싱/"
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        new_posts = []
        items = soup.select('.item')
        for post in items[:5]:
            try:
                link_tag = post.find('a')
                if link_tag:
                    link = "https://imginn.org" + link_tag['href']
                    caption = post.find('img')['alt'] if post.find('img') else "내용 없음"
                    if link not in seen_instagram:
                        seen_instagram.add(link)
                        if "문의" in caption or "질문" in caption or len(seen_instagram) <= 5:
                            post_msg = f"📸 [인스타 새 글 감지]\n\n📝 내용: {caption[:40]}...\n\n🔗 바로가기: {link}"
                            new_posts.append(post_msg)
            except: continue
        if new_posts:
            for p in new_posts: send_telegram(p)
    except: pass

def instagram_timer():
    while True:
        check_instagram()
        delay = 3600 + random.randint(0, 600)
        print(f"인스타 대기: {delay}")
        time.sleep(delay)

def send_telegram(text):
    try: requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage", params={"chat_id": CHAT_ID, "text": text}, timeout=10)
    except: pass

def monitor_commands():
    last_id = 0
    print("🚀 진단 봇 시작")
    send_telegram("🚀 봇 업데이트 완료!\n이제 /경제 를 누르면 AI가 왜 안 되는지 영문 에러를 알려줍니다.")
    
    while True:
        try:
            res = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates", params={"offset": last_id + 1, "timeout": 20}).json()
            for up in res.get("result", []):
                last_id = up["update_id"]
                txt = up.get("message", {}).get("text", "")
                
                if txt == "/?": send_telegram("❓ 메뉴\n/정보: 나라장터 & 인기통\n/경제: AI 뉴스 브리핑")
                elif txt == "/정보": send_telegram(get_info())
                elif txt == "/경제": send_telegram(get_economy())
            time.sleep(1)
        except: time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=instagram_timer, daemon=True).start()
    monitor_commands()

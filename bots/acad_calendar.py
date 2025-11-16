# acad_calendar_monthly_webhook.py
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from datetime import datetime
import os
import requests
from dotenv import load_dotenv 
load_dotenv() # .env 파일 읽어오기

YEAR = datetime.now().year
URL = f"https://www.uts.edu.au/for-students/current-students/managing-your-course/important-dates/academic-year-dates/{YEAR}-academic-year-dates"

SEMESTERS = {
    "Autumn": "collapsible-0",
    "Spring": "collapsible-1",
    "Summer": "collapsible-2",
}

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12
}

def parse_date_range(date_str):
    date_str = date_str.lower()
    months_in_text = [MONTHS[m] for m in MONTHS if m in date_str]
    if not months_in_text:
        return None
    return months_in_text[0], months_in_text[-1]

def fetch_all_events():
    """모든 학기 이벤트 크롤링"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL)
        for sem_id in SEMESTERS.values():
            try:
                page.eval_on_selector(f"#{sem_id}", "el => el.setAttribute('aria-hidden', 'false')")
            except Exception as e:
                print(f"⚠ Could not open {sem_id}: {e}")
        html = page.content()
        browser.close()

    soup = BeautifulSoup(html, "html.parser")
    events = []
    for sem_name, sem_id in SEMESTERS.items():
        collapsible = soup.find("div", id=sem_id)
        if not collapsible:
            continue
        for table in collapsible.find_all("table"):
            for row in table.find_all("tr"):
                cols = row.find_all("td")
                if len(cols) != 2:
                    continue
                event_name = cols[0].get_text(strip=True)
                date_range = cols[1].get_text(strip=True)
                parsed_range = parse_date_range(date_range)
                events.append({
                    "session": sem_name,
                    "event": event_name,
                    "date_range": date_range,
                    "month_range": parsed_range
                })
    return events

def get_events_for_month(events, month):
    """이번 달에 해당하는 이벤트만 필터링"""
    month_events = []
    for e in events:
        if not e["month_range"]:
            continue
        start, end = e["month_range"]
        if start <= month <= end:
            month_events.append(e)
    return month_events

def send_discord_via_webhook(message):
    """Webhook으로 디스코드 메시지 전송"""
    webhook_url = os.environ.get("ACADEMIC_WEBHOOK_URL")
    if not webhook_url:
        print("⚠ ACADEMIC_WEBHOOK_URL이 설정되지 않았습니다.")
        return
    data = {"content": message}
    resp = requests.post(webhook_url, json=data)
    if resp.status_code == 204:
        print("✅ 메시지 전송 완료 via Webhook")
    else:
        print(f"⚠ 메시지 전송 실패: {resp.status_code}, {resp.text}")

if __name__ == "__main__":
    now = datetime.now()
    all_events = fetch_all_events()
    month_events = get_events_for_month(all_events, now.month)

    if not month_events:
        msg = f"📅 {now.year}년 {now.strftime('%B')} UTS Academic Events 📅\n\n이번 달에는 등록된 학사 일정이 없습니다."
    else:
        msg_lines = [f"📅 {now.year}년 {now.strftime('%B')} UTS Academic Events 📅\n"]
        for e in month_events:
            msg_lines.append(f"- [{e['session']}] {e['event']}: {e['date_range']}")
        msg = "\n".join(msg_lines)

    send_discord_via_webhook(msg)

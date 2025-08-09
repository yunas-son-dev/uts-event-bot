import os
import asyncio
import discord
from dotenv import load_dotenv
from playwright.async_api import async_playwright
import datetime

# ✅ 1. 환경변수 로드
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))

# ✅ 2. 디스코드 클라이언트 선언
intents = discord.Intents.default()
client = discord.Client(intents=intents)

# ✅ 3. 이벤트 크롤링 함수 (비동기)
async def scrape_events():
    print("🕸️ Scraping 시작")
    try:
        BASE_URL = "https://www.activateuts.com.au/events/?orderby=featured"
        events = []
        today = datetime.date.today()
        start_of_week = today - datetime.timedelta(days=today.weekday())
        end_of_week = start_of_week + datetime.timedelta(days=6)
        page_num = 1
        has_more = True

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            while has_more:
                url = f"{BASE_URL}&page_num={page_num}"
                page = await browser.new_page()
                print(f"🌐 페이지 열기 중... {url}")
                await page.goto(url, timeout=60000)
                await page.wait_for_selector("div.tile.tile--event", timeout=60000)
                cards = await page.query_selector_all("div.tile.tile--event")
                print(f"📦 이벤트 카드 수 (page {page_num}): {len(cards)}")

                if not cards:
                    has_more = False
                    await page.close()
                    break

                for card in cards:
                    date_str = await (await card.query_selector("span.tile__badge")).inner_text()
                    try:
                        # 기간(예: '14 JUL - 31 OCT') 또는 단일 날짜(예: '5 AUG')
                        parts = date_str.strip().split()
                        if '-' in date_str:
                            # 기간 처리
                            # 예: '14 JUL - 31 OCT' 또는 '4 AUG - 10 AUG'
                            # 시작일: parts[0] parts[1], 종료일: parts[3] parts[4]
                            if len(parts) >= 5 and parts[2] == '-':
                                start_day = int(parts[0])
                                start_month = parts[1]
                                end_day = int(parts[3])
                                end_month = parts[4]
                                year = today.year
                                start_date = datetime.datetime.strptime(f"{start_day} {start_month} {year}", "%d %b %Y").date()
                                end_date = datetime.datetime.strptime(f"{end_day} {end_month} {year}", "%d %b %Y").date()
                            else:
                                continue
                        elif len(parts) >= 2:
                            try:
                                day = int(parts[0])
                                month = parts[1]
                                year = today.year
                                start_date = end_date = datetime.datetime.strptime(f"{day} {month} {year}", "%d %b %Y").date()
                            except Exception as e:
                                continue
                        else:
                            continue
                    except Exception as e:
                        print("❌ 날짜 파싱 실패:", date_str, e)
                        continue

                    # 이번 주와 겹치는 이벤트만 추가
                    if end_date < start_of_week or start_date > end_of_week:
                        continue

                    title = await (await card.query_selector("h3.tile__title")).inner_text()
                    desc = await (await card.query_selector("p.tile__desc")).inner_text()
                    href = await (await card.query_selector("a")).get_attribute("href")
                    full_link = f"https://www.activateuts.com.au{href}"
                    events.append((date_str.strip(), title.strip(), desc.strip(), full_link))

                await page.close()
                # 카드가 15개 미만이면 마지막 페이지로 간주하고 종료
                if len(cards) < 15:
                    has_more = False
                else:
                    page_num += 1

            await browser.close()
            print("🧹 브라우저 종료")
            return events
    except Exception as e:
        print("❌ Scraping error:", e)
        return []

# ✅ 4. 디스코드 봇 동작 정의
@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

    channel = client.get_channel(CHANNEL_ID)
    print("📡 Channel object:", channel)

    if channel is None:
        print("❌ 채널을 찾을 수 없습니다. 채널 ID 또는 권한 확인 필요!")
    else:
        events = await scrape_events()

        # 단일 날짜(기간이 아닌) 이벤트만 필터링
        single_day_events = [e for e in events if '-' not in e[0]]

        if not single_day_events:
            msg = "**🎉 Upcoming UTS Events This Week!**\n\n😢 이번 주 예정된 단일 날짜 이벤트가 없습니다. 나중에 다시 확인해 주세요!"
            await channel.send(msg)
        else:
            header = "**🎉 Upcoming UTS Events This Week!**\n\n"
            chunks = []
            current_chunk = header
            for date, title, desc, link in single_day_events:
                event_msg = f"📆 {date} | 📌 {title}\n🔗 <{link}>\n📝 {desc}\n\n"
                # 만약 현재 chunk에 추가하면 2000자를 넘는다면, 새 chunk로 시작
                if len(current_chunk) + len(event_msg) > 2000:
                    chunks.append(current_chunk)
                    current_chunk = event_msg
                else:
                    current_chunk += event_msg
            if current_chunk.strip():
                chunks.append(current_chunk)

            for chunk in chunks:
                await channel.send(chunk)
            print("✅ 메시지 전송 완료")

    await client.close()

# ✅ 5. 실행
if __name__ == "__main__":
    asyncio.run(client.start(DISCORD_TOKEN))

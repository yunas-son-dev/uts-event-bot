import asyncio
import re
from urllib.parse import urlparse
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

BASE_URL = (
    "https://au.prosple.com/search-jobs?"
    "locations=9692&defaults_applied=1&study_fields=502"
    "&industry_sectors=762&work_rights=29061%2C29063"
)
PAGE_SIZE = 20
MAX_PAGES = 10  # GitHub Actions timeout guard (was 50)

SYDNEY_RE = re.compile(r"\b(Sydney|NSW)\b", re.I)

# route rules
ALLOW_PREFIXES = (
    "/job/",
    "/graduate-jobs/",
    "/graduate-employers/",
)

BLOCK_SUBSTRINGS = (
    "/advice",
    "/career-advice",
    "/resources",
    "/events",
    "/virtual-experiences",
    "/student-competitions",
    "/talent-trial",
    "/workshops",
    "/news",
    "/discover",
    "/stories",
)

TITLE_EXCLUDE_RE = re.compile(
    r"(how to|resume|cover letter|talent trial|workshop|webinar|guide)",
    re.I,
)

def _slug_to_company(href: str) -> str:
    """
    /graduate-employers/<slug>/jobs-internships/... 에서 <slug>를 회사명으로 변환
    """
    try:
        path = urlparse(href).path
    except Exception:
        path = href
    parts = [p for p in path.split("/") if p]
    company = ""
    if len(parts) >= 2 and parts[0] == "graduate-employers":
        slug = parts[1]
        company = " ".join(
            w.capitalize() if w.lower() != "tiktok" else "TikTok"
            for w in slug.split("-")
        )
        company = company.replace(" And ", " & ")
    return company or "Unknown"


async def scrape_prosple_it():
    print("[prosple] Starting scrape...")
    jobs = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-gpu",
                "--disable-dev-shm-usage",
            ],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 1600},
            locale="en-US",
        )
        # stealth-like
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
            Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
        """)

        page = await context.new_page()

        async def maybe_close_banners():
            for sel in [
                "button:has-text('Accept')",
                "button:has-text('Agree')",
                "button:has-text('OK')",
                "button:has-text('Got it')",
                "button[aria-label='Close']",
            ]:
                try:
                    btn = page.locator(sel)
                    if await btn.count():
                        await btn.first.click(timeout=500)
                        await page.wait_for_timeout(150)
                except Exception:
                    pass

        # pagination loop
        for page_idx in range(MAX_PAGES):
            start = page_idx * PAGE_SIZE
            url = f"{BASE_URL}&start={start}"
            print(f"[prosple] Loading: {url}")
            await page.goto(url, timeout=60000, wait_until="domcontentloaded")
            await maybe_close_banners()
            try:
                await page.wait_for_load_state("networkidle", timeout=8000)
            except PlaywrightTimeout:
                pass

            anchors = page.locator(
                "h2 a[href^='/graduate-employers/'], "
                "h2 a[href^='/job/'], "
                "h2 a[href^='/graduate-jobs/']"
            )

            # scroll to load more results
            for _ in range(6):
                if await anchors.count() > 0:
                    break
                await page.mouse.wheel(0, 2000)
                await page.wait_for_timeout(600)

            count = await anchors.count()
            print(f"[prosple] Found {count} job links on page {page_idx+1}")

            if count == 0:  # end when no more results
                print(f"[prosple] No more results. Stop at page {page_idx+1}")
                break

            if page_idx == MAX_PAGES - 1:
                print(f"[prosple] Warning: hit MAX_PAGES={MAX_PAGES} cap – there may be more results.")

            # parsing job cards
            for i in range(count):
                a = anchors.nth(i)
                try:
                    href = await a.get_attribute("href")
                    if not href:
                        continue

                    path_for_check = urlparse(href).path if "://" in href else href

                    # 1) blocklist cut
                    if any(bad in path_for_check for bad in BLOCK_SUBSTRINGS):
                        continue
                    # 2) allowlist check
                    if not path_for_check.startswith(ALLOW_PREFIXES):
                        continue
                    # 3) exclude titles
                    title = (await a.inner_text()).strip()
                    if TITLE_EXCLUDE_RE.search(title):
                        continue

                    # link normalization
                    link = href if href.startswith("http") else f"https://au.prosple.com{href}"

                    # card element
                    card = a.locator("xpath=ancestor::li[1]")
                    if not await card.count():
                        card = a.locator("xpath=ancestor::div[1]")

                    # location
                    location = ""
                    try:
                        loc_node = card.locator(
                            "xpath=.//*[self::p or self::span]"
                            "[contains(translate(normalize-space(.),"
                            "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'sydney') "
                            "or contains(., 'NSW')]"
                        ).first
                        if await loc_node.count():
                            location = (await loc_node.inner_text()).strip()
                    except Exception:
                        pass
                    if not SYDNEY_RE.search(location or ""):
                        continue

                    # salary
                    salary = ""
                    try:
                        sal_node = card.locator("span", has_text="AUD").first
                        if await sal_node.count():
                            salary = (await sal_node.inner_text()).strip()
                    except Exception:
                        pass

                    # start date
                    start_date = ""
                    try:
                        label = card.locator("div:has-text('Start Date')")
                        if await label.count():
                            sib = label.first.locator("xpath=following-sibling::*[1]")
                            if await sib.count():
                                start_date = (await sib.inner_text()).strip()
                    except Exception:
                        pass

                    company = _slug_to_company(path_for_check)
                    role = title

                    jobs.append((company, role, location, salary, start_date, link))

                except Exception as e:
                    print(f"[prosple] Error parsing a card: {e}")
                    continue

        await context.close()
        await browser.close()

    print(f"[prosple] Returning {len(jobs)} Sydney jobs")
    return jobs


if __name__ == "__main__":
    asyncio.run(scrape_prosple_it())

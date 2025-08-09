# bots/prosple.py
import os, asyncio
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from playwright.async_api import async_playwright

DEFAULT_URL = os.getenv(
    "PROSPLE_URL",
    "https://au.prosple.com/search-jobs?defaults_applied=1&industry_sectors=762&work_rights=29061&start=0&locations=9692%2C9692%7C9694%2C9692%7C9694%7C24308"
)
KEYWORDS = [s.strip().lower() for s in os.getenv(
    "PROSPLE_KEYWORDS",
    "software,devops,sre,cloud,backend,python,aws,golang,kubernetes"
).split(",")]

MAX_PAGES = int(os.getenv("PROSPLE_MAX_PAGES", "3"))
PAGE_SIZE = int(os.getenv("PROSPLE_PAGE_SIZE", "20"))  # Prosple usually uses 20 per page

def _with_start(url: str, start: int) -> str:
    """Change the 'start' value in the query for pagination."""
    parsed = urlparse(url)
    q = parse_qs(parsed.query)
    q["start"] = [str(start)]
    new_query = urlencode({k: v[0] if isinstance(v, list) else v for k, v in q.items()})
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))

async def scrape_prosple_it():
    """
    Returns: List[(date, title, desc, link)]
    """
    base_url = DEFAULT_URL
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        for i in range(MAX_PAGES):
            start = i * PAGE_SIZE
            list_url = _with_start(base_url, start)
            print(f"🌐 Prosple page: {list_url}")

            # Retry loading up to 3 times
            for attempt in range(3):
                try:
                    await page.goto(list_url, timeout=60000)
                    # Wait for job links to load
                    # Prosple job link pattern: /graduate-jobs/ or /job/
                    await page.wait_for_selector("a[href*='/graduate-jobs/'], a[href*='/job/']", timeout=60000)
                    break
                except Exception as e:
                    if attempt == 2:
                        raise
                    await asyncio.sleep(2 * (attempt + 1))

            anchors = await page.query_selector_all("a[href*='/graduate-jobs/'], a[href*='/job/']")
            if not anchors:
                # No more results, stop
                break

            seen = set()  # Prevent duplicates if the same anchor appears multiple times
            for a in anchors:
                try:
                    href = await a.get_attribute("href")
                    if not href or href in seen:
                        continue
                    seen.add(href)
                    link = href if href.startswith("http") else f"https://au.prosple.com{href}"

                    # Prefer anchor text for title
                    title = (await a.inner_text()).strip()
                    if not title:
                        # Try to get title from nearby elements
                        parent = await a.element_handle()
                        if parent:
                            h = await parent.query_selector("h3, h2, .job-title")
                            if h:
                                title = (await h.inner_text()).strip()
                    if not title:
                        continue

                    # Try to extract summary/description and date from nearby container
                    desc = ""
                    date_txt = "New"
                    parent = await a.element_handle()
                    if parent:
                        container = await parent.evaluate_handle("el => el.closest('article, li, .search-result, .node, .card')")
                        if container:
                            d = await container.query_selector("p, .summary, .field--name-body, .field--name-field-teaser")
                            if d:
                                try:
                                    desc = (await d.inner_text()).strip()
                                except:
                                    pass
                            t = await container.query_selector("time, .posted, .date, .created")
                            if t:
                                try:
                                    date_txt = (await t.inner_text()).strip() or date_txt
                                except:
                                    pass

                    # Keyword filter (title + description)
                    hay = (title + " " + desc).lower()
                    if not any(k in hay for k in KEYWORDS):
                        continue

                    results.append((date_txt, title, desc, link))
                except Exception:
                    continue

            # Short sleep before moving to next page (politeness)
            await asyncio.sleep(0.8)

        await browser.close()

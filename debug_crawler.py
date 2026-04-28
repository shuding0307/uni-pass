import asyncio
from playwright.async_api import async_playwright

async def dump_html():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://curriculum.kangwon.ac.kr/bbs/board.php?bo_table=sub2_5", wait_until="networkidle")
        content = await page.content()
        with open("page_dump.html", "w", encoding="utf-8") as f:
            f.write(content)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(dump_html())

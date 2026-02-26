from playwright.sync_api import sync_playwright

def render_page(url: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )

        page = browser.new_page()
        page.set_extra_http_headers({
            "Accept-Language": "en-US,en;q=0.9"
        })

        # IMPORTANT: avoid networkidle
        page.goto(url, wait_until="domcontentloaded", timeout=60000)

        # Wait for DOM + SPA hydration
        page.wait_for_selector("body", timeout=15000)
        page.wait_for_timeout(3000)

        html = page.content()
        browser.close()

        return html

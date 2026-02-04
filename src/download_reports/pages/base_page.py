"""Base page class with common functionality."""

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError
from typing import Optional


class BasePage:
    def __init__(self, page: Page, timeout: int = 30000):
        self.page = page
        self.timeout = timeout
    
    async def wait_for_element(self, locator: str, state: str = "visible") -> bool:
        try:
            await self.page.locator(locator).wait_for(state=state, timeout=self.timeout)
            return True
        except PlaywrightTimeoutError:
            return False
    
    async def click_element(self, locator: str) -> bool:
        try:
            if await self.wait_for_element(locator, "visible"):
                await self.page.locator(locator).click()
                return True
            return False
        except Exception:
            return False
    
    async def fill_input(self, locator: str, value: str) -> bool:
        try:
            if await self.wait_for_element(locator, "visible"):
                await self.page.locator(locator).fill(value)
                return True
            return False
        except Exception:
            return False

    async def clear_and_type(self, locator: str, value: str) -> bool:
        """Clear then fill (useful for search inputs)."""
        try:
            if not await self.wait_for_element(locator, "visible"):
                return False
            el = self.page.locator(locator)
            await el.click()
            await el.fill("")
            await el.fill(value)
            return True
        except Exception:
            return False
    
    async def get_text(self, locator: str) -> Optional[str]:
        try:
            if await self.wait_for_element(locator, "visible"):
                text = await self.page.locator(locator).text_content()
                return text.strip() if text else None
            return None
        except Exception:
            return None
    
    async def is_enabled(self, locator: str) -> bool:
        try:
            if await self.wait_for_element(locator, "visible"):
                return await self.page.locator(locator).is_enabled()
            return False
        except Exception:
            return False
    
    async def wait_for_url(self, url_pattern: str, timeout: Optional[int] = None) -> bool:
        try:
            await self.page.wait_for_url(
                lambda url: url_pattern in url,
                timeout=timeout or self.timeout
            )
            return True
        except PlaywrightTimeoutError:
            return False

    async def set_value_js(self, locator: str, value: str) -> bool:
        """Set value via JS and dispatch input/change events."""
        try:
            handle = self.page.locator(locator).first
            await handle.evaluate(
                "(el, val) => { el.value = val; el.dispatchEvent(new Event('input', {bubbles:true})); el.dispatchEvent(new Event('change', {bubbles:true})); }",
                value,
            )
            return True
        except Exception:
            return False

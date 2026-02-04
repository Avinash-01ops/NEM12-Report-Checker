"""Login page object."""

from playwright.async_api import Page
from .base_page import BasePage


class LoginPage(BasePage):
    EMAIL_INPUT = '//input[@id="signInName"]'
    PASSWORD_INPUT = '//input[@id="password"]'
    SIGNIN_BUTTON = '//button[@id="next"]'
    
    def __init__(self, page: Page, timeout: int = 30000):
        super().__init__(page, timeout)
    
    async def navigate(self, url: str) -> bool:
        try:
            await self.page.goto(url, wait_until="networkidle", timeout=self.timeout)
            return True
        except Exception:
            return False
    
    async def enter_email(self, email: str) -> bool:
        return await self.fill_input(self.EMAIL_INPUT, email)
    
    async def enter_password(self, password: str) -> bool:
        return await self.fill_input(self.PASSWORD_INPUT, password)
    
    async def click_signin(self) -> bool:
        if not await self.is_enabled(self.SIGNIN_BUTTON):
            return False
        return await self.click_element(self.SIGNIN_BUTTON)

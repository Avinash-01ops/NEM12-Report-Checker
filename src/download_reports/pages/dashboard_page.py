"""Dashboard page object."""

from playwright.async_api import Page
from .base_page import BasePage


class DashboardPage(BasePage):
    REPORTS_MENU = '//*[@title="Reports"]'
    NEM12_REPORT_LINK = '//*[@title="NEM12 Report"]'
    
    def __init__(self, page: Page, timeout: int = 30000):
        super().__init__(page, timeout)
    
    async def verify_dashboard_url(self, expected_url: str) -> bool:
        return await self.wait_for_url(expected_url)
    
    async def click_reports_menu(self) -> bool:
        if await self.click_element(self.REPORTS_MENU):
            await self.page.wait_for_timeout(500)
            return True
        return False
    
    async def click_nem12_report(self) -> bool:
        if await self.click_element(self.NEM12_REPORT_LINK):
            await self.page.wait_for_load_state("networkidle", timeout=self.timeout)
            return True
        return False

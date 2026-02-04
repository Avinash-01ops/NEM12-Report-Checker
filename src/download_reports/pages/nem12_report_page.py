"""NEM12 Report page object."""

from playwright.async_api import Page
from .base_page import BasePage


class NEM12ReportPage(BasePage):
    PAGE_TITLE = '//*[@class="card-title mb-0"]'

    # Search/list view
    SEARCH_INPUT = '//input[@id="name"]'
    SEARCH_BUTTON = '//button[text()="Search"]'
    RESULT_NAME_SPAN = '//span[@title="{name}"]'
    RESULT_VIEW_NAME_INPUT = '//input[@value="{name}"]'
    BACK_BUTTON = '//button//span[text()=" Back"]'
    ROW_CHECKBOX_BY_NAME = '//div[@role="row"]//span[@title="{name}"]/ancestor::div[@role="row"]//input[@type="checkbox"]'
    EXECUTE_BUTTON = '//button[contains(@class,"btn-secondary") and .//i[contains(@class,"fa-calendar")] and contains(.,"Execute")]'

    # View mode fields
    FALLBACK_INTERVAL = '//input[@id="fallback_interval_length"]'
    MISSING_DATA_SELECT = '//select[@id="missing_data_handling"]'
    CUM_SUB_SINGLE_VALUE = '//input[@id="cumulative_sub_type"]/ancestor::div[contains(@class,"css-ru69us-control")]//div[contains(@class,"singleValue")]'
    EXCLUDE_NULL_CHECKBOX = '//h5[contains(.,"Exclude null")]/ancestor::div[contains(@class,"card-header")]//input[@type="checkbox"]'

    # Execute modal
    MODAL = '//div[contains(@class,"modal-content")]'
    MODAL_FROM_INPUT = '//div[contains(@class,"modal-content")]//label[contains(.,"From Date")]/ancestor::div[contains(@class,"form-group")]//input[@type="text"]'
    MODAL_TO_INPUT = '//div[contains(@class,"modal-content")]//label[contains(.,"To Date")]/ancestor::div[contains(@class,"form-group")]//input[@type="text"]'
    MODAL_EXECUTE_BUTTON = '//div[contains(@class,"modal-content")]//div[contains(@class,"modal-footer")]//button[contains(.,"Execute")]'
    MODAL_HEADER = '//div[contains(@class,"modal-content")]//div[contains(@class,"modal-header")]'

    # Success alert (match the visible SweetAlert popup)
    SUCCESS_ALERT_CONTAINER = '//div[contains(@class,"sweet-alert") and contains(@style,"display: flex")]'
    SUCCESS_OK = SUCCESS_ALERT_CONTAINER + '//a[contains(@class,"btn-primary")]'
    
    def __init__(self, page: Page, timeout: int = 30000):
        super().__init__(page, timeout)
    
    async def verify_page_title(self, expected_title: str) -> bool:
        title_text = await self.get_text(self.PAGE_TITLE)
        return title_text == expected_title

    async def search_report(self, report_name: str) -> bool:
        # Ensure search input is editable, clear, type
        if not await self.wait_for_element(self.SEARCH_INPUT, "visible"):
            return False
        if not await self.page.locator(self.SEARCH_INPUT).is_editable():
            return False
        if not await self.clear_and_type(self.SEARCH_INPUT, report_name):
            return False
        return await self.click_element(self.SEARCH_BUTTON)

    async def wait_for_result(self, report_name: str) -> bool:
        locator = self.RESULT_NAME_SPAN.format(name=report_name)
        return await self.wait_for_element(locator, "visible")

    async def open_result_view(self, report_name: str) -> bool:
        locator = self.RESULT_NAME_SPAN.format(name=report_name)
        if not await self.click_element(locator):
            return False
        # Verify view mode by checking name input value exists
        return await self.wait_for_element(self.RESULT_VIEW_NAME_INPUT.format(name=report_name), "visible")

    async def read_metadata(self, report_name: str) -> dict:
        # FallBack Interval
        fallback = ""
        try:
            fallback = (await self.page.locator(self.FALLBACK_INTERVAL).input_value()).strip()
        except Exception:
            fallback = ""

        # Missing Data Handling
        missing_value = ""
        missing_label = ""
        try:
            sel = self.page.locator(self.MISSING_DATA_SELECT)
            missing_value = (await sel.input_value()).strip()
            if missing_value:
                opt = self.page.locator(f'{self.MISSING_DATA_SELECT}/option[@value="{missing_value}"]')
                missing_label = (await opt.text_content() or "").strip()
        except Exception:
            missing_value, missing_label = "", ""

        # Cumulative substitution type (react-select single value)
        cum_sub = (await self.get_text(self.CUM_SUB_SINGLE_VALUE)) or ""

        # Exclude null checkbox
        exclude_null = False
        try:
            exclude_null = await self.page.locator(self.EXCLUDE_NULL_CHECKBOX).is_checked()
        except Exception:
            exclude_null = False

        return {
            "report_name": report_name,
            "fallback_interval": fallback,
            "missing_data_handling_value": missing_value,
            "missing_data_handling_label": missing_label,
            "cumulative_substitution_type": cum_sub,
            "exclude_null": exclude_null,
        }

    async def click_back(self) -> bool:
        return await self.click_element(self.BACK_BUTTON)

    async def select_report_checkbox(self, report_name: str) -> bool:
        locator = self.ROW_CHECKBOX_BY_NAME.format(name=report_name)
        if not await self.wait_for_element(locator, "visible"):
            return False
        cb = self.page.locator(locator)
        if await cb.is_checked():
            return True
        await cb.click()
        return await cb.is_checked()

    async def click_execute(self) -> bool:
        if not await self.click_element(self.EXECUTE_BUTTON):
            return False
        return await self.wait_for_element(self.MODAL, "visible")

    @staticmethod
    def _parse_date_ddmmyyyy(date_str: str):
        # Returns (day, month_index0, year)
        parts = date_str.split("/")
        if len(parts) != 3:
            return None
        day = int(parts[0])
        month = int(parts[1]) - 1  # 0-based for data-month
        year = int(parts[2])
        return day, month, year

    async def _select_date_from_picker(self, input_locator: str, date_str: str) -> bool:
        parsed = self._parse_date_ddmmyyyy(date_str)
        if not parsed:
            return False
        target_day, target_month0, target_year = parsed

        # Click input to open picker
        if not await self.click_element(input_locator):
            return False

        # Scope picker relative to the input (first following picker)
        picker = self.page.locator(f'{input_locator}/following::div[contains(@class,"rdtPicker")][1]')
        header = picker.locator('xpath=.//th[contains(@class,"rdtSwitch")]').first
        prev_btn = picker.locator('xpath=.//th[contains(@class,"rdtPrev")]').first
        next_btn = picker.locator('xpath=.//th[contains(@class,"rdtNext")]').first

        month_map = {
            "January": 0, "February": 1, "March": 2, "April": 3, "May": 4, "June": 5,
            "July": 6, "August": 7, "September": 8, "October": 9, "November": 10, "December": 11
        }

        async def get_header_month_year():
            text = (await header.text_content() or "").strip()
            parts = text.split()
            if len(parts) != 2:
                return None
            month_name, year = parts[0], int(parts[1])
            if month_name not in month_map:
                return None
            return month_map[month_name], year

        # Navigate months to target
        for _ in range(36):  # guard to prevent infinite loop
            current = await get_header_month_year()
            if not current:
                break
            cur_month, cur_year = current
            if cur_month == target_month0 and cur_year == target_year:
                break
            if (cur_year, cur_month) > (target_year, target_month0):
                await prev_btn.click()
            else:
                await next_btn.click()
            await self.page.wait_for_timeout(100)

        # Click the day cell (filter out disabled/old/new classes)
        day_locator = picker.locator(f'xpath=.//td[@data-year="{target_year}"][@data-month="{target_month0}"][@data-value="{target_day}"][not(contains(@class,"rdtDisabled"))][not(contains(@class,"rdtOld"))][not(contains(@class,"rdtNew"))]')
        try:
            await day_locator.first.click(timeout=5000)
            await self.page.wait_for_timeout(100)
        except Exception:
            return False

        # Click the time toggle (set to time view) if present
        time_toggle = picker.locator('xpath=.//td[contains(@class,"rdtTimeToggle")]').first
        try:
            await time_toggle.click(timeout=3000)
            await self.page.wait_for_timeout(100)
        except Exception:
            pass

        # Force value via JS to ensure 00:00
        target_value = f"{date_str} 00:00"
        await self.set_value_js(input_locator, target_value)
        await self.page.wait_for_timeout(100)
        
        # Close picker by clicking modal header (outside picker)
        try:
            await self.page.locator(self.MODAL_HEADER).click(timeout=2000)
            await self.page.wait_for_timeout(100)
        except Exception:
            pass
        return True

    async def execute_with_dates(self, from_date: str, to_date: str) -> bool:
        if not await self.wait_for_element(self.MODAL, "visible"):
            return False
        await self.page.wait_for_timeout(300)
        
        if not await self._select_date_from_picker(self.MODAL_FROM_INPUT, from_date):
            return False
        await self.page.wait_for_timeout(200)
        
        if not await self._select_date_from_picker(self.MODAL_TO_INPUT, to_date):
            return False
        await self.page.wait_for_timeout(200)
        
        # Click Execute
        if not await self.click_element(self.MODAL_EXECUTE_BUTTON):
            return False
        await self.page.wait_for_timeout(500)
        
        # Wait for success alert container
        container = self.page.locator(self.SUCCESS_ALERT_CONTAINER).first
        try:
            await container.wait_for(state="visible", timeout=10000)
        except Exception:
            return False

        # Click OK button (force if needed)
        ok_button = self.page.locator(self.SUCCESS_OK).first
        try:
            await ok_button.click(timeout=5000, force=True)
            await self.page.wait_for_timeout(500)
            return True
        except Exception:
            return False

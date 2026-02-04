"""View Reports page object."""

from datetime import datetime
from typing import List, Optional, Dict
from playwright.async_api import Page
from .base_page import BasePage
from utils.logger import Logger


class ViewReportsPage(BasePage):
    LINK_VIEW_REPORTS = '//a[@title="View Reports"]'
    TITLE_VIEW_REPORTS = '//h5[text()="View Reports"]'
    REPORT_TYPE_SELECT = '//select[@id="report_type"]'
    REPORT_TYPE_OPTION_NEM12 = '//select[@id="report_type"]/option[@value="NEM12ReportExecutionLogs" and normalize-space()="NEM12"]'
    REPORT_NAME_INPUT = '//input[@id="report_name"]'
    SEARCH_BUTTON = '//button[text()="Search"]'
    LOADING = '//div[contains(@class,"-loading") and contains(.,"Loading")]'

    # New robust locators based on report name
    REPORT_NAME_SPAN = '//span[normalize-space()="{name}"]'
    ROW_BY_REPORT_NAME = '//span[normalize-space()="{name}"]/ancestor::div[@role="row"]'
    TIMESTAMP_BY_REPORT_NAME = '//span[normalize-space()="{name}"]/ancestor::div[@role="row"]//div[7]//span'
    STATUS_BY_REPORT_NAME = '//span[normalize-space()="{name}"]/ancestor::div[@role="row"]//span[contains(@class,"badge")]'
    ACTION_BUTTON_BY_REPORT_NAME = '//span[normalize-space()="{name}"]/ancestor::div[@role="row"]//span[@data-toggle="dropdown"]'
    DOWNLOAD_BUTTON_BY_REPORT_NAME = '//span[normalize-space()="{name}"]/ancestor::div[@role="row"]//button[@title="Download"]'
    
    # Legacy locators (kept for fallback)
    ROW_GROUPS = '//div[@class="rt-tr-group"]'
    CELL_REPORT_NAME = './/span[@title]'
    CELL_STATUS = './/span[contains(@class,"badge")]'
    CELL_TIMESTAMP = './/span[@title][last()]'
    ACTION_TOGGLE = './/div[contains(@class,"td-dropdown-toggle")]//span'
    ACTION_DOWNLOAD = './/div[contains(@class,"dropdown-menu")]//button[contains(@title,"Download")]'

    def __init__(self, page: Page, timeout: int = 30000):
        super().__init__(page, timeout)

    async def open(self) -> bool:
        if not await self.click_element(self.LINK_VIEW_REPORTS):
            return False
        return await self.wait_for_element(self.TITLE_VIEW_REPORTS, "visible")

    async def set_report_type_nem12(self) -> bool:
        """Select NEM12 in the report type dropdown using select_option (more stable)."""
        try:
            select = self.page.locator(self.REPORT_TYPE_SELECT)
            await select.select_option("NEM12ReportExecutionLogs")
            return True
        except Exception:
            return False

    async def search_report(self, name: str) -> bool:
        if not await self.clear_and_type(self.REPORT_NAME_INPUT, name):
            return False
        await self.page.wait_for_timeout(300)
        
        # Verify input was filled correctly
        input_value = await self.page.locator(self.REPORT_NAME_INPUT).input_value()
        if input_value != name:
            # Try filling again
            await self.page.locator(self.REPORT_NAME_INPUT).fill(name)
            await self.page.wait_for_timeout(300)
        
        try:
            # Search button is sometimes overlaid; use short timeout + force.
            search_btn = self.page.locator(self.SEARCH_BUTTON).first
            await search_btn.wait_for(state="visible", timeout=5000)
            await search_btn.click(timeout=5000, force=True)
        except Exception as e:
            return False

        # If loading spinner shows up, wait for it to hide; otherwise continue quickly.
        try:
            loading = self.page.locator(self.LOADING).first
            await loading.wait_for(state="visible", timeout=1000)
            await loading.wait_for(state="hidden", timeout=20000)
        except Exception:
            pass
        return True

    async def find_execution_by_name(self, name: str, target_ts: Optional[datetime] = None) -> Optional[Dict]:
        """
        Find execution row by report name using robust XPath locators.
        Returns dict with name, status, timestamp, and row locator.
        """
        try:
            # Wait for table to be visible
            await self.page.wait_for_timeout(1000)
            
            # Check if report name span exists
            name_locator = self.REPORT_NAME_SPAN.format(name=name)
            name_elements = self.page.locator(name_locator)
            count = await name_elements.count()
            
            if count == 0:
                return None
            
            # Get all matching rows - iterate through each report name instance
            matches = []
            for i in range(count):
                try:
                    # Get the specific name element and its parent row
                    name_el = name_elements.nth(i)
                    
                    # Get the row ancestor for this specific name instance
                    row = name_el.locator('xpath=./ancestor::div[@role="row"]')
                    
                    # Extract status relative to this row
                    status_el = row.locator('xpath=.//span[contains(@class,"badge")]').first
                    status = ""
                    try:
                        status = (await status_el.text_content() or "").strip()
                    except Exception:
                        pass
                    
                    # Extract timestamp relative to this row (div[7]//span)
                    ts_el = row.locator('xpath=.//div[7]//span').first
                    ts_raw = ""
                    try:
                        ts_raw = (await ts_el.get_attribute("title") or 
                                 await ts_el.text_content() or "").strip()
                    except Exception:
                        pass
                    
                    # Parse timestamp (format: dd-mm-YYYY HH:MM)
                    ts = None
                    if ts_raw:
                        try:
                            ts = datetime.strptime(ts_raw, "%d-%m-%Y %H:%M")
                        except ValueError:
                            # Try alternative formats
                            try:
                                ts = datetime.strptime(ts_raw, "%d-%m-%Y %H:%M:%S")
                            except ValueError:
                                pass
                    
                    matches.append({
                        "name": name,
                        "status": status,
                        "timestamp": ts,
                        "row": row,
                        "index": i
                    })
                except Exception as e:
                    continue
            
            if not matches:
                return None
            
            # Filter matches with valid timestamps
            valid_matches = [m for m in matches if m["timestamp"] is not None]
            if not valid_matches:
                # Return first match even without timestamp
                return matches[0] if matches else None
            
            # If we have a target execution timestamp, find the closest match
            if target_ts is not None:
                # Prefer matches at or after the target timestamp
                after_matches = [m for m in valid_matches if m["timestamp"] >= target_ts]
                if after_matches:
                    # Sort by closest to target timestamp
                    after_matches.sort(key=lambda r: abs((r["timestamp"] - target_ts).total_seconds()))
                    return after_matches[0]
                else:
                    # If no matches after target, get the closest before
                    valid_matches.sort(key=lambda r: abs((r["timestamp"] - target_ts).total_seconds()))
                    return valid_matches[0]
            
            # Fallback: return latest by timestamp
            valid_matches.sort(key=lambda r: r["timestamp"], reverse=True)
            return valid_matches[0]
            
        except Exception as e:
            return None

    async def find_latest_by_name(self, name: str, target_ts: Optional[datetime] = None) -> Optional[Dict]:
        """Legacy method - now uses find_execution_by_name"""
        return await self.find_execution_by_name(name, target_ts)

    async def download_row(self, row, report_name: str) -> bool:
        """
        Download report by clicking the action toggle and download button.
        Uses new XPath locators based on report name.
        """
        try:
            # Use new XPath locators based on report name
            action_button_locator = self.ACTION_BUTTON_BY_REPORT_NAME.format(name=report_name)
            download_button_locator = self.DOWNLOAD_BUTTON_BY_REPORT_NAME.format(name=report_name)
            
            # Click action button (dropdown toggle) to open dropdown
            Logger.info(f"Clicking action button for report: {report_name}")
            action_button = self.page.locator(action_button_locator).first
            await action_button.wait_for(state="visible", timeout=10000)
            await action_button.click(timeout=10000)
            await self.page.wait_for_timeout(500)  # Wait for dropdown to open
            
            # Click download button
            Logger.info(f"Clicking download button for report: {report_name}")
            download_button = self.page.locator(download_button_locator).first
            await download_button.wait_for(state="visible", timeout=10000)
            await download_button.click(timeout=10000)
            await self.page.wait_for_timeout(500)
            return True
        except Exception as e:
            Logger.error(f"Download failed: {str(e)}")
            return False

#!/usr/bin/env python3
"""NEM12 Report Downloader - MetrixAI portal automation."""

import asyncio
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from playwright.async_api import async_playwright

# Load .env explicitly from project root
ROOT_DIR = Path(__file__).resolve().parents[2]
try:
    from dotenv import load_dotenv, dotenv_values  # type: ignore
    env_path = ROOT_DIR / ".env"
    load_dotenv(dotenv_path=env_path)
    # Fallback: if still missing, read values directly and set
    if not os.getenv("METRIXA_EMAIL") or not os.getenv("METRIXA_PASSWORD"):
        vals = dotenv_values(env_path)
        for k, v in vals.items():
            if k and v:
                os.environ.setdefault(k, v)
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).parent))
from pages.login_page import LoginPage
from pages.dashboard_page import DashboardPage
from pages.nem12_report_page import NEM12ReportPage
from pages.view_reports_page import ViewReportsPage
from utils.logger import Logger
from datetime import timezone
import config  # type: ignore[attr-defined]

# Type ignore for config module attributes (they exist at runtime but linter doesn't recognize them)
# pyright: reportAttributeAccessIssue=false
# pylint: disable=no-member


class NEM12Downloader:
    def __init__(self):
        self.email = os.getenv("METRIXA_EMAIL")
        self.password = os.getenv("METRIXA_PASSWORD")
        self.download_dir = config.DOWNLOAD_DIR
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        if not self.email or not self.password:
            raise ValueError("Missing credentials in .env file")
    
    async def run(self) -> bool:
        Logger.info("NEM12 Report Downloader")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            # Set up download path
            context = await browser.new_context(accept_downloads=True)
            page = await context.new_page()
            
            # Track download
            download_info = {"download": None, "completed": False}
            
            async def handle_download(download):
                download_info["download"] = download
                Logger.info(f"Download started: {download.suggested_filename}")
            
            page.on("download", handle_download)
            
            try:
                login = LoginPage(page, config.TIMEOUT)
                dashboard = DashboardPage(page, config.TIMEOUT)
                nem12 = NEM12ReportPage(page, config.TIMEOUT)
                view = ViewReportsPage(page, config.TIMEOUT)
                
                Logger.step(1, f"Navigate: {config.LOGIN_URL}")
                if not await login.navigate(config.LOGIN_URL):
                    return False
                
                Logger.step(2, "Enter credentials")
                if not await login.enter_email(self.email or ""):
                    return False
                if not await login.enter_password(self.password or ""):
                    return False
                
                Logger.step(3, "Click signin")
                if not await login.click_signin():
                    return False
                
                Logger.step(4, "Verify dashboard")
                if not await dashboard.verify_dashboard_url(config.DASHBOARD_URL):
                    return False
                
                Logger.step(5, "Click Reports menu")
                if not await dashboard.click_reports_menu():
                    return False
                
                Logger.step(6, "Click NEM12 Report")
                if not await dashboard.click_nem12_report():
                    return False
                
                Logger.step(7, "Verify page")
                if not await nem12.verify_page_title(config.EXPECTED_PAGE_TITLE):
                    return False

                # Step 8: Search report
                Logger.step(8, "Search report")
                if not await nem12.search_report(config.REPORT_NAME):
                    return False

                Logger.step(9, "Verify result")
                if not await nem12.wait_for_result(config.REPORT_NAME):
                    return False

                Logger.step(10, "Open report (view)")
                if not await nem12.open_result_view(config.REPORT_NAME):
                    return False

                Logger.step(11, "Read metadata")
                meta = await nem12.read_metadata(config.REPORT_NAME)
                meta_out = config.METADATA_OUT
                meta_out.parent.mkdir(parents=True, exist_ok=True)
                with open(meta_out, "w", encoding="utf-8") as f:
                    json.dump(meta, f, indent=2)

                Logger.step(12, "Back to list")
                if not await nem12.click_back():
                    return False

                Logger.step(13, "Select checkbox")
                if not await nem12.select_report_checkbox(config.REPORT_NAME):
                    return False

                Logger.step(14, "Execute")
                if not await nem12.click_execute():
                    return False

                Logger.step(15, "Set dates + confirm")
                if not await nem12.execute_with_dates(config.EXECUTE_FROM_DATE, config.EXECUTE_TO_DATE):
                    Logger.error("Failed executing with dates")
                    return False

                # Capture execution timestamp in UTC (used to find the exact run)
                exec_ts_utc = datetime.now(timezone.utc).replace(tzinfo=None)  # Remove timezone for comparison
                exec_ts_str = exec_ts_utc.strftime('%d-%m-%Y %H:%M')
                Logger.info(f"Recorded execution timestamp (UTC): {exec_ts_str}")

                # Save execution timestamp to metadata
                meta["execution_timestamp_utc"] = exec_ts_str
                meta["execution_timestamp_datetime"] = exec_ts_utc.isoformat()
                with open(meta_out, "w", encoding="utf-8") as f:
                    json.dump(meta, f, indent=2)

                # Go to View Reports and poll status
                Logger.step(16, "Open View Reports")
                if not await view.open():
                    Logger.error("Failed to open View Reports")
                    return False

                Logger.step(17, "Set report type NEM12")
                if not await view.set_report_type_nem12():
                    Logger.error("Failed to set report type to NEM12")
                    return False
                await page.wait_for_timeout(500)

                Logger.step(18, "Search executions")
                if not await view.search_report(config.REPORT_NAME):
                    Logger.error("Failed to search for report executions")
                    return False
                
                # Wait for search results to load
                Logger.info("Waiting for search results to load...")
                await page.wait_for_timeout(3000)
                
                # Wait for loading spinner to disappear if present
                try:
                    loading = page.locator(view.LOADING).first
                    await loading.wait_for(state="visible", timeout=2000)
                    await loading.wait_for(state="hidden", timeout=15000)
                    Logger.info("Loading spinner disappeared")
                except Exception:
                    Logger.info("No loading spinner detected")
                
                await page.wait_for_timeout(2000)
                Logger.info("Execution search submitted. Waiting for results...")

                # Test: Verify we can find the report name in the table
                Logger.step(18.1, "Verify report appears in results")
                test_name_locator = view.REPORT_NAME_SPAN.format(name=config.REPORT_NAME)
                
                # Debug: Check if any spans with the report name exist
                all_spans = page.locator('//span')
                span_count = await all_spans.count()
                Logger.info(f"Debug: Found {span_count} span elements on page")
                
                # Try to find report name with different approaches
                found = False
                try:
                    await page.locator(test_name_locator).wait_for(state="visible", timeout=10000)
                    found = True
                    Logger.info(f"[OK] Report name '{config.REPORT_NAME}' found in results table")
                except Exception as e:
                    Logger.info(f"[WARN] Report name not found with exact match. Trying case-insensitive...")
                    # Try case-insensitive search
                    try:
                        # Try finding any span containing the report name
                        case_insensitive = f'//span[contains(translate(text(), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "{config.REPORT_NAME.lower()}")]'
                        await page.locator(case_insensitive).first.wait_for(state="visible", timeout=5000)
                        found = True
                        Logger.info(f"[OK] Report name found with case-insensitive search")
                    except Exception:
                        pass
                
                if not found:
                    Logger.error(f"[FAIL] Report name '{config.REPORT_NAME}' not found in results table")
                    Logger.info("Waiting additional 5 seconds for results to load...")
                    await page.wait_for_timeout(5000)
                    # Try again
                    try:
                        await page.locator(test_name_locator).wait_for(state="visible", timeout=10000)
                        found = True
                        Logger.info(f"[OK] Report name '{config.REPORT_NAME}' found after retry")
                    except Exception:
                        Logger.error("[FAIL] Report still not found. Check if search worked correctly.")
                        Logger.info("Debug: Checking if search input has the correct value...")
                        search_input_value = await page.locator(view.REPORT_NAME_INPUT).input_value()
                        Logger.info(f"Debug: Search input value is: '{search_input_value}'")
                        Logger.info("Debug: Check browser window to see if results are displayed")
                        return False

                # Test: Verify we can read timestamp and status
                Logger.step(18.2, "Test reading timestamp and status")
                test_match = await view.find_execution_by_name(config.REPORT_NAME, exec_ts_utc)
                if test_match:
                    ts_str = test_match["timestamp"].strftime("%d-%m-%Y %H:%M") if test_match["timestamp"] else "UNKNOWN"
                    Logger.info(f"[OK] Found execution: Status='{test_match['status']}', Timestamp='{ts_str}'")
                else:
                    Logger.info("[WARN] No execution found yet (this is normal if execution just started)")

                Logger.info(f"Polling every {config.POLL_INTERVAL_SECONDS}s for completion (max {config.POLL_MAX_MINUTES} minutes)")
                Logger.info("Page will refresh every 120 seconds to get latest status updates")

                max_cycles = max(1, int((config.POLL_MAX_MINUTES * 60) / config.POLL_INTERVAL_SECONDS))
                latest_status = "UNKNOWN"
                refresh_interval_seconds = 120  # Refresh page every 120 seconds
                cycles_since_refresh = 0
                cycles_per_refresh = max(1, int(refresh_interval_seconds / config.POLL_INTERVAL_SECONDS))
                
                for idx in range(max_cycles):
                    await page.wait_for_timeout(500)
                    
                    # Check if we need to refresh the page (every 120 seconds)
                    if cycles_since_refresh >= cycles_per_refresh:
                        Logger.info(f"[Refresh] Refreshing page to get latest status (after {cycles_since_refresh * config.POLL_INTERVAL_SECONDS} seconds)")
                        await page.reload()
                        await page.wait_for_timeout(2000)
                        
                        # Re-set report type to NEM12
                        Logger.info("[Refresh] Re-setting report type to NEM12")
                        if not await view.set_report_type_nem12():
                            Logger.error("[Refresh] Failed to set report type after refresh")
                            return False
                        await page.wait_for_timeout(1000)
                        
                        # Re-search for report name
                        Logger.info(f"[Refresh] Re-searching for report: {config.REPORT_NAME}")
                        if not await view.search_report(config.REPORT_NAME):
                            Logger.error("[Refresh] Failed to search for report after refresh")
                            return False
                        
                        # Wait for search results to load
                        Logger.info("[Refresh] Waiting for search results to load...")
                        await page.wait_for_timeout(3000)
                        
                        # Wait for loading spinner to disappear if present
                        try:
                            loading = page.locator(view.LOADING).first
                            await loading.wait_for(state="visible", timeout=2000)
                            await loading.wait_for(state="hidden", timeout=20000)
                            Logger.info("[Refresh] Loading spinner disappeared")
                        except Exception:
                            Logger.info("[Refresh] No loading spinner detected")
                        
                        await page.wait_for_timeout(2000)
                        
                        # Verify report appears after refresh
                        test_name_locator = view.REPORT_NAME_SPAN.format(name=config.REPORT_NAME)
                        try:
                            await page.locator(test_name_locator).wait_for(state="visible", timeout=10000)
                            Logger.info(f"[Refresh] Report name '{config.REPORT_NAME}' found after refresh")
                        except Exception:
                            # Try case-insensitive
                            try:
                                case_insensitive = f'//span[contains(translate(text(), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "{config.REPORT_NAME.lower()}")]'
                                await page.locator(case_insensitive).first.wait_for(state="visible", timeout=10000)
                                Logger.info(f"[Refresh] Report name found with case-insensitive search")
                            except Exception:
                                Logger.error(f"[Refresh] Report name '{config.REPORT_NAME}' not found after refresh")
                                return False
                        
                        cycles_since_refresh = 0
                        Logger.info("[Refresh] Page refreshed and settings restored. Continuing polling...")
                    
                    match = await view.find_execution_by_name(config.REPORT_NAME, exec_ts_utc)
                    if match:
                        latest_status = match["status"]
                        ts_str = match["timestamp"].strftime("%d-%m-%Y %H:%M") if match["timestamp"] else "UNKNOWN"
                        Logger.info(f"[Log {idx+1}] Report '{match['name']}' at {ts_str} UTC -> Status: {latest_status}")
                        status_l = latest_status.lower()
                        if status_l == "completed":
                            Logger.step(19, "Download report")
                            if not await view.download_row(match["row"], config.REPORT_NAME):
                                Logger.error("Download click failed")
                                return False
                            Logger.success("Download initiated successfully")
                            
                            # Wait for download to complete
                            Logger.info("Waiting for download to complete...")
                            max_wait = 60  # Wait up to 60 seconds for download
                            waited = 0
                            while download_info["download"] is None and waited < max_wait:
                                await page.wait_for_timeout(1000)
                                waited += 1
                            
                            if download_info["download"] is None:
                                Logger.error("Download did not start within timeout")
                                return False
                            
                            # Wait for download to finish
                            try:
                                download = download_info["download"]
                                
                                # Wait for download to complete (this blocks until file is downloaded)
                                Logger.info("Waiting for file download to finish...")
                                original_path = await download.path()
                                Logger.success("Download completed")
                                
                                # Get original filename
                                original_filename = download.suggested_filename
                                
                                # Load metadata to get report name and dates
                                meta_path = config.METADATA_OUT  # type: ignore
                                meta = {}
                                if meta_path.exists():
                                    with open(meta_path, "r", encoding="utf-8") as f:
                                        meta = json.load(f)
                                
                                report_name = meta.get("report_name", config.REPORT_NAME)  # type: ignore
                                
                                # Get dates from config and convert to YYYYMMDD format
                                from_date_str = config.EXECUTE_FROM_DATE  # type: ignore  # Format: DD/MM/YYYY
                                to_date_str = config.EXECUTE_TO_DATE  # type: ignore  # Format: DD/MM/YYYY
                                
                                try:
                                    from_date = datetime.strptime(from_date_str, "%d/%m/%Y")
                                    to_date = datetime.strptime(to_date_str, "%d/%m/%Y")
                                    from_date_formatted = from_date.strftime("%Y%m%d")
                                    to_date_formatted = to_date.strftime("%Y%m%d")
                                except Exception:
                                    Logger.info(f"Could not parse dates from config, using defaults")
                                    from_date_formatted = "00000000"
                                    to_date_formatted = "00000000"
                                
                                # Extract NMI from downloaded file (first record type 200)
                                nmi_number = "UNKNOWN_NMI"
                                try:
                                    Logger.info("Extracting NMI from downloaded file...")
                                    with open(original_path, 'r', encoding='utf-8') as f:
                                        for line in f:
                                            line = line.strip()
                                            if not line:
                                                continue
                                            # Detect delimiter
                                            delimiter = ',' if ',' in line else ('|' if '|' in line else '\t')
                                            parts = line.split(delimiter)
                                            if len(parts) > 1 and parts[0].strip() == '200':
                                                # Record type 200: NMI is at index 1
                                                nmi_number = parts[1].strip() if len(parts) > 1 else "UNKNOWN_NMI"
                                                Logger.info(f"Found NMI: {nmi_number}")
                                                break
                                except Exception as e:
                                    Logger.info(f"Could not extract NMI from file: {str(e)}")
                                    nmi_number = "UNKNOWN_NMI"
                                
                                # Prompt user for Before/After - this determines folder and filename
                                Logger.info("\n" + "="*60)
                                Logger.info("REPORT TYPE SELECTION")
                                Logger.info("="*60)
                                Logger.info("Which type of report is this?")
                                Logger.info("  - BEFORE: Report before changes (saves to Before_Production folder)")
                                Logger.info("  - AFTER:  Report after changes (saves to After_Production folder)")
                                Logger.info("="*60)
                                
                                event_type = None
                                target_dir = None
                                
                                while True:
                                    user_input = input("\nEnter 'Before' or 'After' (or 'B'/'A'): ").strip().lower()
                                    if user_input in ['before', 'b']:
                                        event_type = "BEFORE"
                                        target_dir = Path("D:/Projects/nem12_validator-main - Copy/data/Before_Production")
                                        Logger.info(f"Selected: BEFORE report")
                                        break
                                    elif user_input in ['after', 'a']:
                                        event_type = "AFTER"
                                        target_dir = Path("D:/Projects/nem12_validator-main - Copy/data/After_Production")
                                        Logger.info(f"Selected: AFTER report")
                                        break
                                    else:
                                        Logger.error("Invalid input. Please enter 'Before' or 'After' (or 'B'/'A').")
                                
                                # Create target directory if it doesn't exist
                                target_dir.mkdir(parents=True, exist_ok=True)
                                Logger.info(f"Target directory: {target_dir}")
                                
                                # Create new filename: ReportName_NMINO_FROMDATE-TODATE_EVENT.ext
                                # Clean report name for filename (remove special characters)
                                clean_report_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in report_name)
                                clean_report_name = clean_report_name.replace(' ', '_')
                                
                                # Get file extension from original filename
                                if '.' in original_filename:
                                    ext = original_filename.rsplit('.', 1)[1]
                                else:
                                    ext = "nem12"  # Default extension
                                
                                # Construct new filename
                                new_filename = f"{clean_report_name}_{nmi_number}_{from_date_formatted}-{to_date_formatted}_{event_type}.{ext}"
                                
                                target_path = target_dir / new_filename
                                
                                # Move file to target directory with new name
                                Logger.info(f"Moving file to: {target_path}")
                                shutil.move(str(original_path), str(target_path))
                                
                                Logger.success("="*60)
                                Logger.success("FILE SAVED SUCCESSFULLY")
                                Logger.success("="*60)
                                Logger.success(f"Location: {target_path}")
                                Logger.success(f"Filename: {new_filename}")
                                Logger.success(f"Format: ReportName_NMI_FromDate-ToDate_Event")
                                Logger.success(f"  - Report Name: {clean_report_name}")
                                Logger.success(f"  - NMI: {nmi_number}")
                                Logger.success(f"  - Date Range: {from_date_formatted}-{to_date_formatted}")
                                Logger.success(f"  - Event Type: {event_type}")
                                Logger.success("="*60)
                                
                                return True
                                
                            except Exception as e:
                                Logger.error(f"Error handling download: {str(e)}")
                                import traceback
                                Logger.error(traceback.format_exc())
                                return False
                        if status_l == "failed":
                            Logger.error("Report execution failed")
                            return False
                    else:
                        Logger.info(f"[Log {idx+1}] No executions found yet for '{config.REPORT_NAME}'. Retrying...")
                    
                    cycles_since_refresh += 1
                    await page.wait_for_timeout(config.POLL_INTERVAL_SECONDS * 1000)

                Logger.error(f"Timeout waiting for completion (last status: {latest_status})")
                return False
                
            except KeyboardInterrupt:
                return False
            except Exception as e:
                Logger.error(str(e))
                return False
            finally:
                await browser.close()


async def main():
    try:
        downloader = NEM12Downloader()
        success = await downloader.run()
        sys.exit(0 if success else 1)
    except ValueError as e:
        Logger.error(f"Config error: {e}")
        sys.exit(1)
    except Exception as e:
        Logger.error(f"Fatal: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

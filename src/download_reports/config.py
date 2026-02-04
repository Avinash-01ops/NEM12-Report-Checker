"""Downloader configuration."""

from pathlib import Path

BASE_URL = "https://metrixaidev.autoind.com.au"
LOGIN_URL = f"{BASE_URL}/"
DASHBOARD_URL = f"{BASE_URL}/dashboard"
EXPECTED_PAGE_TITLE = "NEM12 Report"
REPORT_NAME = "Utopia Electricity CET"
# Dates in DD/MM/YYYY format
EXECUTE_FROM_DATE = "01/11/2025"
EXECUTE_TO_DATE = "02/11/2025"

# Future downloads can be saved here
DOWNLOAD_DIR = Path("Data/Downloaded_Reports")
METADATA_OUT = Path("Results/report_metadata.json")
TIMEOUT = 30000

# View Reports polling (UTC timestamp format dd-mm-YYYY HH:MM)
POLL_MAX_MINUTES = 25
POLL_INTERVAL_SECONDS = 30

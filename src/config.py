import os
import configparser
from pathlib import Path

CONFIG_PATHS = [Path("configs/config.ini"), Path(".env")]


def load_config(path=None):
    """Load configuration from an ini file or environment variables.

    Returns a dict with sections as keys.
    """
    config = {}
    parser = configparser.ConfigParser()
    if path and Path(path).exists():
        parser.read(path)
        for section in parser.sections():
            config[section] = dict(parser[section])
    else:
        # Fallback to environment variables for two DBs
        config["meter_db"] = {
            "host": os.environ.get("METER_DB_HOST"),
            "port": os.environ.get("METER_DB_PORT"),
            "database": os.environ.get("METER_DB_NAME"),
            "user": os.environ.get("METER_DB_USER"),
            "password": os.environ.get("METER_DB_PASSWORD"),
        }
        config["report_db"] = {
            "host": os.environ.get("REPORT_DB_HOST"),
            "port": os.environ.get("REPORT_DB_PORT"),
            "database": os.environ.get("REPORT_DB_NAME"),
            "user": os.environ.get("REPORT_DB_USER"),
            "password": os.environ.get("REPORT_DB_PASSWORD"),
        }
    return config

import psycopg2
import psycopg2.extras
import logging

logger = logging.getLogger(__name__)


def connect_db(conn_info: dict):
    """Establish and return a psycopg2 connection using a dict of connection info.

    Expects keys: host, port, database, user, password. Optionally sslmode.
    """
    if not conn_info:
        raise ValueError("Connection info is required")
    conn_params = {
        "host": conn_info.get("host") or conn_info.get("Server"),
        "port": conn_info.get("port") or conn_info.get("Port"),
        "database": conn_info.get("database") or conn_info.get("Database"),
        "user": conn_info.get("user") or conn_info.get("User Id") or conn_info.get("username"),
        "password": conn_info.get("password") or conn_info.get("Password"),
    }
    # Optional sslmode
    if conn_info.get("sslmode"):
        conn_params["sslmode"] = conn_info.get("sslmode")
    try:
        conn = psycopg2.connect(**conn_params)
        return conn
    except Exception as e:
        logger.exception("Failed to connect to database: %s", e)
        raise

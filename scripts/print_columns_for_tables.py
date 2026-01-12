from src.db import connect_db

REPORT_DB = {
    'host': 'ai-mdm-test-qa.postgres.database.azure.com',
    'port': '5432',
    'database': 'pgdb-reports-test-qa',
    'user': 'tatva_readonly',
    'password': '6Yopc4msdqKeoMDn'
}


TABLES = [
    'nem12_report',
    'nem12_report_output',
    'nem12_report_output_channels',
    'nem12_report_meters',
    'nem12_report_output_channels',
    'nem12_report_output'
]


def print_columns(conn, table):
    cur = conn.cursor()
    try:
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s ORDER BY ordinal_position", (table,))
        rows = cur.fetchall()
        print(f"\nColumns for {table}:")
        for r in rows:
            print('-', r[0])
    finally:
        try:
            cur.close()
        except Exception:
            pass


def main():
    conn = connect_db(REPORT_DB)
    try:
        for t in TABLES:
            print_columns(conn, t)
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == '__main__':
    main()

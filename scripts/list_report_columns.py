from src.db import connect_db

REPORT_DB = {
    'host': 'ai-mdm-test-qa.postgres.database.azure.com',
    'port': '5432',
    'database': 'pgdb-reports-test-qa',
    'user': 'tatva_readonly',
    'password': '6Yopc4msdqKeoMDn'
}


def main():
    conn = connect_db(REPORT_DB)
    try:
        cur = conn.cursor()
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s", ('nem12_report',))
        rows = cur.fetchall()
        print('nem12_reports columns:')
        for r in rows:
            print('-', r[0])
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == '__main__':
    main()

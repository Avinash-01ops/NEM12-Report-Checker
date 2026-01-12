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
        cur.execute("""
        SELECT table_schema, table_name FROM information_schema.tables
        WHERE table_type='BASE TABLE' AND (table_name ILIKE '%nem%' OR table_name ILIKE '%report%')
        ORDER BY table_schema, table_name
        """)
        rows = cur.fetchall()
        print('Matching tables:')
        for schema, name in rows:
            print(f"{schema}.{name}")
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == '__main__':
    main()

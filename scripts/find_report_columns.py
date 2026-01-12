"""Find columns in the report DB that match common interval/energy names."""
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
        SELECT table_name, column_name FROM information_schema.columns
        WHERE column_name ILIKE ANY (ARRAY['%interval%','%start%','%time%','%energy%','%value%','%reading%'])
        ORDER BY table_name, ordinal_position
        """)
        rows = cur.fetchall()
        if not rows:
            print('No matching columns found')
            return
        current = None
        for table, col in rows:
            if table != current:
                print(f"\nTable: {table}")
                current = table
            print('-', col)
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == '__main__':
    main()

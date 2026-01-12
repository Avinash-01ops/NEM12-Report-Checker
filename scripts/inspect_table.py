import sys
import psycopg2

METER_DB = {
    'host': 'ai-metrix-dev1-autoind-327e.a.timescaledb.io',
    'port': '25897',
    'database': 'mdm-dev',
    'user': 'tatva_readonly',
    'password': 'ILsNhjI5fETbkWyc'
}

REPORT_DB = {
    'host': 'ai-mdm-test-qa.postgres.database.azure.com',
    'port': '5432',
    'database': 'pgdb-reports-test-qa',
    'user': 'tatva_readonly',
    'password': '6Yopc4msdqKeoMDn'
}


def inspect_table(db_config, table_name):
    try:
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()
        cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = %s ORDER BY ordinal_position", (table_name,))
        rows = cur.fetchall()
        if not rows:
            print(f"No columns found for {table_name}")
            return
        print(f"Columns for {table_name}:")
        for col, dtype in rows:
            print(f"- {col}: {dtype}")
    except Exception as e:
        print(f"Error inspecting {table_name}: {e}")
    finally:
        try:
            conn.close()
        except:
            pass


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: inspect_table.py <meter|report> <table_name>')
        sys.exit(1)
    which = sys.argv[1]
    table = sys.argv[2]
    cfg = METER_DB if which == 'meter' else REPORT_DB
    inspect_table(cfg, table)

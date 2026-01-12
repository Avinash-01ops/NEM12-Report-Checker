"""Comprehensive schema discovery for both meter and report databases."""
from src.db import connect_db

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


def show_table_structure(conn, table_name):
    """Show columns and sample row count for a table."""
    cur = conn.cursor()
    try:
        cur.execute("""
        SELECT column_name, data_type FROM information_schema.columns
        WHERE table_name = %s ORDER BY ordinal_position
        """, (table_name,))
        cols = cur.fetchall()
        
        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cur.fetchone()[0]
        
        print(f"\nTable: {table_name} ({count} rows)")
        print("Columns:")
        for col, dtype in cols:
            print(f"  - {col}: {dtype}")
    except Exception as e:
        print(f"Error querying {table_name}: {e}")
    finally:
        try:
            cur.close()
        except:
            pass


def discover_meter_db():
    print("=" * 60)
    print("METER DATABASE (mdm-dev)")
    print("=" * 60)
    conn = connect_db(METER_DB)
    try:
        # Find all tables
        cur = conn.cursor()
        cur.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """)
        tables = [r[0] for r in cur.fetchall()]
        cur.close()
        
        print(f"Total tables: {len(tables)}")
        print("Tables:", ', '.join(tables))
        
        # Show structure of key tables
        for t in ['meter', 'meter_channel', 'meter_data']:
            if t in tables:
                show_table_structure(conn, t)
    finally:
        try:
            conn.close()
        except:
            pass


def discover_report_db():
    print("\n" + "=" * 60)
    print("REPORT DATABASE (pgdb-reports-test-qa)")
    print("=" * 60)
    conn = connect_db(REPORT_DB)
    try:
        # Find all tables
        cur = conn.cursor()
        cur.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """)
        tables = [r[0] for r in cur.fetchall()]
        cur.close()
        
        print(f"Total tables: {len(tables)}")
        
        # Show structure of NEM12-related tables
        nem_tables = [t for t in tables if 'nem12' in t.lower() or 'report_output' in t.lower()]
        print(f"NEM12/Report tables ({len(nem_tables)}): {', '.join(nem_tables)}")
        
        for t in nem_tables[:10]:  # Show first 10 to avoid too much output
            show_table_structure(conn, t)
    finally:
        try:
            conn.close()
        except:
            pass


if __name__ == '__main__':
    discover_meter_db()
    discover_report_db()

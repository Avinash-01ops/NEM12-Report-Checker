import psycopg2

METER_DB = {
    'host': 'ai-metrix-dev1-autoind-327e.a.timescaledb.io',
    'port': '25897',
    'database': 'mdm-dev',
    'user': 'tatva_readonly',
    'password': 'ILsNhjI5fETbkWyc'
}

conn = psycopg2.connect(**METER_DB)
try:
    cur = conn.cursor()
    cur.execute("""
    SELECT table_name FROM information_schema.tables
    WHERE table_schema = 'public' AND table_type = 'BASE TABLE' AND (table_name ILIKE '%meter%' OR table_name ILIKE '%reading%')
    ORDER BY table_name
    """)
    rows = cur.fetchall()
    print('Matching tables:')
    for (t,) in rows:
        print('-', t)
finally:
    try:
        conn.close()
    except:
        pass

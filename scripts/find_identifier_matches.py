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


def find_in_meters(identifier):
    conn = psycopg2.connect(**METER_DB)
    try:
        cur = conn.cursor()
        # Try numeric id match and string matches
        try:
            iid = int(identifier)
        except Exception:
            iid = None
        if iid is not None:
            cur.execute("SELECT id, meter_id, nmi FROM meters WHERE id = %s LIMIT 5", (iid,))
            rows = cur.fetchall()
            if rows:
                print('Found by id in meters:')
                for r in rows:
                    print(r)
        cur.execute("SELECT id, meter_id, nmi FROM meters WHERE meter_id = %s OR nmi = %s LIMIT 5", (identifier, identifier))
        rows = cur.fetchall()
        if rows:
            print('Found by meter_id/nmi in meters:')
            for r in rows:
                print(r)
    finally:
        try:
            conn.close()
        except:
            pass


def find_in_report_data(identifier, report_id=None):
    conn = psycopg2.connect(**REPORT_DB)
    try:
        cur = conn.cursor()
        print('\nSearching data_validation_report_rule_output_data for exact meter_id matches...')
        cur.execute("SELECT id, rule_output_id, meter_id, channel_name, value, timestamp FROM data_validation_report_rule_output_data WHERE meter_id = %s LIMIT 10", (identifier,))
        rows = cur.fetchall()
        if rows:
            for r in rows:
                print(r)
        else:
            print('No exact matches found for meter_id in data_validation_report_rule_output_data')

        if report_id is not None:
            print(f"\nChecking nem12_report_meters for report {report_id}...")
            cur.execute("SELECT id, nem12_report_id, meter_id FROM nem12_report_meters WHERE nem12_report_id = %s AND (meter_id = %s) LIMIT 10", (report_id, identifier))
            rows = cur.fetchall()
            if rows:
                for r in rows:
                    print(r)
            else:
                print('No nem12_report_meters rows found for that report and meter_id')

    finally:
        try:
            conn.close()
        except:
            pass


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: find_identifier_matches.py <identifier> [report_id]')
        sys.exit(1)
    identifier = sys.argv[1]
    report_id = sys.argv[2] if len(sys.argv) > 2 else None
    find_in_meters(identifier)
    find_in_report_data(identifier, report_id)

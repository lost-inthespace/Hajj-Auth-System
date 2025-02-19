import sqlite3
import json

DB_PATH = "local.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    c = conn.cursor()

    # Main Hajj table
    c.execute("""
    CREATE TABLE IF NOT EXISTS hajj_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        hajj_id TEXT UNIQUE,
        name TEXT,
        nfc_data TEXT,  -- JSON: {uid, encrypted_data, decrypted_data}
        fingerprint_data TEXT  -- JSON: {location, template, raw_image, timestamp}
    )
    """)

    conn.commit()
    conn.close()


def create_hajj_record(data):
    conn = get_connection()
    c = conn.cursor()

    nfc_data = json.dumps(data.get('nfc_data', {})) if data.get('nfc_data') else None
    fp_data = json.dumps(data.get('fingerprint_data', {})) if data.get('fingerprint_data') else None

    c.execute("""
    INSERT INTO hajj_records (hajj_id, name, nfc_data, fingerprint_data)
    VALUES (?, ?, ?, ?)
    """, (data['hajj_id'], data['name'], nfc_data, fp_data))

    conn.commit()
    record_id = c.lastrowid

    c.execute("SELECT * FROM hajj_records WHERE id = ?", (record_id,))
    record = c.fetchone()
    conn.close()

    return _convert_record(record) if record else None


def update_hajj_record(hajj_id, new_data):
    conn = get_connection()
    c = conn.cursor()

    # Get existing record
    c.execute("SELECT * FROM hajj_records WHERE hajj_id = ?", (hajj_id,))
    existing = c.fetchone()

    if existing:
        updates = {}
        if 'name' in new_data:
            updates['name'] = new_data['name']

        if 'nfc_data' in new_data:
            current_nfc = json.loads(existing['nfc_data']) if existing['nfc_data'] else {}
            current_nfc.update(new_data['nfc_data'])
            updates['nfc_data'] = json.dumps(current_nfc)

        if 'fingerprint_data' in new_data:
            current_fp = json.loads(existing['fingerprint_data']) if existing['fingerprint_data'] else {}
            current_fp.update(new_data['fingerprint_data'])
            updates['fingerprint_data'] = json.dumps(current_fp)

        if updates:
            query = "UPDATE hajj_records SET " + ", ".join(f"{k} = ?" for k in updates)
            query += " WHERE hajj_id = ?"
            c.execute(query, list(updates.values()) + [hajj_id])
            conn.commit()

        c.execute("SELECT * FROM hajj_records WHERE hajj_id = ?", (hajj_id,))
        record = c.fetchone()
        conn.close()
        return _convert_record(record) if record else None
    else:
        conn.close()
        return create_hajj_record({
            'hajj_id': hajj_id,
            'name': new_data.get('name'),
            'nfc_data': new_data.get('nfc_data'),
            'fingerprint_data': new_data.get('fingerprint_data')
        })


def get_hajj_records():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM hajj_records")
    records = c.fetchall()
    conn.close()
    return [_convert_record(record) for record in records]


def _convert_record(record):
    if not record:
        return None

    result = dict(record)
    if result.get('nfc_data'):
        result['nfc_data'] = json.loads(result['nfc_data'])
    if result.get('fingerprint_data'):
        result['fingerprint_data'] = json.loads(result['fingerprint_data'])
    return result


init_db()
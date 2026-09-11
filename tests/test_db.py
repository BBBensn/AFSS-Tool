from afss.db import get_connection, init_schema


def test_connection_uses_wal_mode_and_busy_timeout(tmp_path):
    db_path = tmp_path / "test.db"
    init_schema(db_path)

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode")
    assert cur.fetchone()[0].lower() == "wal"
    cur.execute("PRAGMA busy_timeout")
    assert cur.fetchone()[0] == 30000
    conn.close()

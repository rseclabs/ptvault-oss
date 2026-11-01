"""Migration 023: Add clients table and link engagements

Promotes the free-text engagements.client_name into a first-class
Clients entity with full contact details (admin contact, technical
contact, address, website, notes). Engagements gain a client_id FK
alongside the existing client_name column.

Backfill: every distinct non-empty engagements.client_name becomes a
clients row, and the corresponding engagements get linked to it. The
free-text client_name column stays in place as a display fallback for
older code paths.

Delete behavior: engagements.client_id uses ON DELETE RESTRICT so the
DAO/route layer can enforce a 409 with an actionable message instead of
SQLite silently nulling rows.

Created: 2026-05-04
"""


def upgrade(db):
    cursor = db.cursor()

    # 1. Create the clients table (idempotent)
    print("  -> Creating clients table")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            admin_contact_name TEXT,
            admin_contact_email TEXT,
            admin_contact_phone TEXT,
            technical_contact_name TEXT,
            technical_contact_email TEXT,
            technical_contact_phone TEXT,
            address TEXT,
            website TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by INTEGER REFERENCES users(id) ON DELETE SET NULL
        )
    ''')
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_clients_name ON clients(name)"
    )

    # 2. Add client_id to engagements (idempotent — guarded for re-runs)
    cursor.execute("PRAGMA table_info(engagements)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'client_id' not in columns:
        print("  -> Adding client_id column to engagements")
        cursor.execute('''
            ALTER TABLE engagements
            ADD COLUMN client_id INTEGER REFERENCES clients(id) ON DELETE RESTRICT
        ''')

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_engagements_client_id "
        "ON engagements(client_id)"
    )

    # 3. Backfill: one clients row per distinct non-empty client_name,
    #    then link the matching engagements.
    cursor.execute('''
        SELECT DISTINCT TRIM(client_name)
        FROM engagements
        WHERE client_name IS NOT NULL
          AND TRIM(client_name) != ''
    ''')
    distinct_names = [row[0] for row in cursor.fetchall()]

    if distinct_names:
        print(f"  -> Backfilling {len(distinct_names)} client(s) "
              f"from existing engagements.client_name")
        for name in distinct_names:
            cursor.execute(
                "INSERT OR IGNORE INTO clients (name) VALUES (?)",
                (name,),
            )
            cursor.execute(
                "SELECT id FROM clients WHERE name = ?", (name,)
            )
            cid = cursor.fetchone()[0]
            cursor.execute(
                "UPDATE engagements SET client_id = ? "
                "WHERE TRIM(client_name) = ? AND client_id IS NULL",
                (cid, name),
            )

    print("  -> Clients migration completed")


def downgrade(db):
    cursor = db.cursor()
    # Engagements lose their FK link first so the table drop won't fail
    # on the reference. SQLite can't easily drop the column on older
    # versions; setting it to NULL is the safe approximation.
    cursor.execute("UPDATE engagements SET client_id = NULL")
    cursor.execute("DROP INDEX IF EXISTS idx_engagements_client_id")
    cursor.execute("DROP INDEX IF EXISTS idx_clients_name")
    cursor.execute("DROP TABLE IF EXISTS clients")

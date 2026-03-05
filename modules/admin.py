"""
Admin & user management — login, user CRUD, permissions, audit log, backups.
"""

from database import get_connection, log_audit, backup_database, hash_password
from datetime import datetime


def authenticate_user(username, password):
    """
    Check credentials and return the user dict if valid, None otherwise.
    Also updates last_login on success.
    """
    conn = get_connection()
    hashed = hash_password(password)

    # Try with the current hashed-password schema first
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE username=? AND password_hash=? AND is_active=1",
            (username, hashed)).fetchone()
    except Exception:
        # If the password_hash column doesn't exist yet (very old DB),
        # fall back to the legacy 'password' column
        try:
            row = conn.execute(
                "SELECT * FROM users WHERE username=? AND password=? AND is_active=1",
                (username, password)).fetchone()
        except Exception:
            row = None

    if row:
        conn.execute("UPDATE users SET last_login=? WHERE user_id=?",
                     (datetime.now().isoformat(), row['user_id']))
        conn.commit()

    conn.close()
    return dict(row) if row else None


def create_user(username, password, full_name, role, email='', admin_id=None):
    """Add a new user account. Returns the new user_id."""
    conn = get_connection()
    try:
        uid = conn.execute(
            "INSERT INTO users (username,password_hash,full_name,role,email) VALUES (?,?,?,?,?)",
            (username, hash_password(password), full_name, role, email)).lastrowid
        log_audit(admin_id, 'CREATE_USER', 'users', uid, None,
                  {'username': username}, conn)
        conn.commit()
        return uid
    except Exception as err:
        conn.rollback()
        raise err
    finally:
        conn.close()


def change_password(user_id, old_pw, new_pw):
    """Verify old password, then set the new one."""
    conn = get_connection()
    row = conn.execute("SELECT user_id FROM users WHERE user_id=? AND password_hash=?",
                       (user_id, hash_password(old_pw))).fetchone()
    if not row:
        conn.close()
        raise ValueError("Current password is incorrect")

    conn.execute("UPDATE users SET password_hash=? WHERE user_id=?",
                 (hash_password(new_pw), user_id))
    conn.commit()
    conn.close()
    return True


def get_all_users():
    """Return a list of all user records (minus password hashes)."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT user_id,username,full_name,role,email,is_active,created_at,last_login "
        "FROM users ORDER BY username").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def check_permission(role, required):
    """Simple role hierarchy check: admin > manager > staff."""
    hierarchy = {'admin': 3, 'manager': 2, 'staff': 1}
    return hierarchy.get(role, 0) >= hierarchy.get(required, 0)


def get_audit_log(limit=100, user_id=None, action=None):
    """Pull recent audit log entries, optionally filtered by user or action."""
    conn = get_connection()
    query = ("SELECT al.*, u.username, u.full_name FROM audit_log al "
             "LEFT JOIN users u ON al.user_id=u.user_id WHERE 1=1")
    params = []

    if user_id:
        query += " AND al.user_id=?"
        params.append(user_id)
    if action:
        query += " AND al.action LIKE ?"
        params.append(f"%{action}%")

    query += " ORDER BY al.timestamp DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def perform_backup(user_id=None):
    """Create a timestamped DB backup and log it."""
    path = backup_database()
    log_audit(user_id, 'BACKUP', None, None, None, {'path': path})
    return path
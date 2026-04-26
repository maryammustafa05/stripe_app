import pyodbc
from contextlib import contextmanager
from dotenv import load_dotenv
from datetime import datetime, timezone
import os

load_dotenv()

connection_string = (
    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
    f"SERVER={os.getenv('DB_HOST')},{os.getenv('DB_PORT', '1433')};"
    f"DATABASE={os.getenv('DB_NAME')};"
    f"UID={os.getenv('DB_USER')};"
    f"PWD={os.getenv('DB_PASSWORD')};"
    f"TrustServerCertificate=yes;"
)

@contextmanager
def get_db():
    conn = pyodbc.connect(connection_string)
    conn.autocommit = False
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def row_to_dict(cursor, row):
    if row is None:
        return None
    columns = [col[0] for col in cursor.description]
    return dict(zip(columns, row))

def unix_to_datetime(timestamp):
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

# ─── User Queries ──────────────────────────────────────────────

def get_user_by_email(email: str):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email = ?", (email,))
        return row_to_dict(cur, cur.fetchone())

def get_user_by_id(user_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        return row_to_dict(cur, cur.fetchone())

def create_user(email: str, hashed_password: str):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO users (email, hashed_password)
            OUTPUT INSERTED.*
            VALUES (?, ?)
            """,
            (email, hashed_password)
        )
        return row_to_dict(cur, cur.fetchone())

def update_user_stripe_customer(user_id: int, stripe_customer_id: str):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET stripe_customer_id = ? WHERE id = ?",
            (stripe_customer_id, user_id)
        )

def get_user_by_stripe_customer(stripe_customer_id: str):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE stripe_customer_id = ?", (stripe_customer_id,))
        return row_to_dict(cur, cur.fetchone())

# ─── Subscription Queries ──────────────────────────────────────

def create_subscription(
    user_id, stripe_subscription_id, stripe_customer_id,
    price_id, status, current_period_start, current_period_end,
):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO subscriptions
                (user_id, stripe_subscription_id, stripe_customer_id, price_id,
                 status, current_period_start, current_period_end)
            OUTPUT INSERTED.*
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id, stripe_subscription_id, stripe_customer_id, price_id,
                status,
                unix_to_datetime(current_period_start),
                unix_to_datetime(current_period_end),
            )
        )
        return row_to_dict(cur, cur.fetchone())

def get_subscription_by_user(user_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT TOP 1 * FROM subscriptions WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        )
        return row_to_dict(cur, cur.fetchone())

def get_subscription_by_stripe_id(stripe_subscription_id: str):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM subscriptions WHERE stripe_subscription_id = ?",
            (stripe_subscription_id,)
        )
        return row_to_dict(cur, cur.fetchone())

def update_subscription_status(
    stripe_subscription_id, status,
    current_period_start=None, current_period_end=None,
    cancel_at_period_end=False,
):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE subscriptions
            SET status = ?,
                current_period_start = COALESCE(?, current_period_start),
                current_period_end   = COALESCE(?, current_period_end),
                cancel_at_period_end = ?,
                updated_at = GETDATE()
            WHERE stripe_subscription_id = ?
            """,
            (
                status,
                unix_to_datetime(current_period_start),
                unix_to_datetime(current_period_end),
                cancel_at_period_end,
                stripe_subscription_id,
            )
        )
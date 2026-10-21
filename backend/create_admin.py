import getpass
import re

from werkzeug.security import generate_password_hash

from app import close_db, get_db_connection


def main():
    username = input("Admin username: ").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.@-]{3,80}", username):
        raise SystemExit("Username must be 3-80 characters: letters, numbers, dot, underscore, @, or hyphen.")

    password = getpass.getpass("Admin password (minimum 12 characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if len(password) < 12:
        raise SystemExit("Password must be at least 12 characters.")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")

    connection = cursor = None
    try:
        connection = get_db_connection()
        connection.start_transaction()
        cursor = connection.cursor()
        cursor.execute("SELECT role_id FROM app_roles WHERE role_name = 'Admin'")
        role = cursor.fetchone()
        if role is None:
            raise SystemExit("RBAC tables are missing. Apply database/migrations/006_application_rbac.sql first.")

        cursor.execute("""
            INSERT INTO app_users (username, password_hash, is_active)
            VALUES (%s, %s, TRUE)
        """, (username, generate_password_hash(password)))
        user_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO app_user_roles (user_id, role_id) VALUES (%s, %s)",
            (user_id, role[0]),
        )
        connection.commit()
        print(f"Admin account '{username}' created.")
    except Exception:
        if connection:
            connection.rollback()
        raise
    finally:
        close_db(cursor, connection)


if __name__ == "__main__":
    main()

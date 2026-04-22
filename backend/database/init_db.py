"""Initialize the database schema.

Usage:
    python -m backend.database.init_db
"""
import sys

from backend.database.session import init_db


def main():
    try:
        init_db()
        print("Database initialized successfully.")
    except Exception as e:
        print("Failed to initialize database:", e)
        raise


if __name__ == "__main__":
    main()

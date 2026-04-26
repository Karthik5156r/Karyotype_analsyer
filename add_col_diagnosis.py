import mysql.connector
from config import get_db_connection

def add_col():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("ALTER TABLE reports ADD COLUMN diagnosis VARCHAR(255)")
        conn.commit()
        print("Diagnosis column added.")
    except Exception as e:
        print("Error/Already exists:", e)
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    add_col()

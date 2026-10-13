
import sqlite3

connection = sqlite3.connect("solar.db")
cursor = connection.cursor()

cursor.execute("""
    SELECT COUNT(*)
    FROM api_requests
""")

total = cursor.fetchone()[0]

print("Toplam API isteği:", total)

cursor.execute("""
    SELECT requested_at, status_code, success
    FROM api_requests
    ORDER BY id DESC
    LIMIT 5
""")

for row in cursor.fetchall():
    print(row)

cursor.execute("""
    SELECT COUNT(*)
    FROM api_requests
    WHERE DATE(requested_at) = DATE('now')
""")

daily_count = cursor.fetchone()[0]

print("Bugünkü API isteği sayısı:", daily_count)

connection.close()

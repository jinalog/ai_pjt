import sqlite3

def main():
    c = sqlite3.connect('app.db')
    tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
    print("TABLES:", tables)
    try:
        print("COUNT places:", c.execute("SELECT COUNT(*) FROM places").fetchone()[0])
    except sqlite3.OperationalError:
        print("COUNT places: (table missing)")

    print('\ntravel_courses sample:')
    try:
        for row in c.execute("SELECT id,title,description FROM travel_courses LIMIT 5"):
            print(row)
    except sqlite3.OperationalError:
        print("travel_courses: (table missing)")

    print('\nmissions sample:')
    try:
        for row in c.execute("SELECT id,course_id,title,reward_points,completed FROM missions LIMIT 5"):
            print(row)
    except sqlite3.OperationalError:
        print("missions: (table missing)")

    c.close()

if __name__ == '__main__':
    main()

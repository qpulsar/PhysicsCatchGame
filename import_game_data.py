import sqlite3
import os
from settings import ALL_QUANTITIES, LEVEL_TARGETS

def create_tables(cursor):
    # Create levels table if not exists
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS levels (
        level_number INTEGER PRIMARY KEY,
        wrong_percentage REAL DEFAULT 30.0,
        item_speed REAL DEFAULT 3.0,
        max_items INTEGER DEFAULT 5
    )
    ''')
    
    # Create expressions table if not exists
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS expressions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        level_number INTEGER,
        expression TEXT NOT NULL,
        is_correct INTEGER DEFAULT 0,
        FOREIGN KEY (level_number) REFERENCES levels(level_number) ON DELETE CASCADE
    )
    ''')
    
    # Create settings table if not exists
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    ''')

def import_levels_and_expressions(cursor):
    # Clear existing data
    cursor.execute('DELETE FROM expressions')
    cursor.execute('DELETE FROM levels')
    
    # Insert levels and their expressions
    for level_num, level_name in LEVEL_TARGETS.items():
        # Insert level
        cursor.execute('''
        INSERT INTO levels (level_number, wrong_percentage, item_speed, max_items)
        VALUES (?, 30.0, 3.0, 5)
        ''', (level_num,))
        
        # Get expressions for this level
        expressions = ALL_QUANTITIES.get(level_name, [])
        
        # Insert expressions for this level
        for expr in expressions:
            cursor.execute('''
            INSERT INTO expressions (level_number, expression, is_correct)
            VALUES (?, ?, 1)
            ''', (level_num, expr))

def import_settings(cursor):
    # Clear existing settings
    cursor.execute('DELETE FROM settings')
    
    # Insert default settings
    settings = [
        ('total_levels', str(len(LEVEL_TARGETS))),
        ('default_wrong_percentage', '30.0'),
        ('default_item_speed', '3.0'),
        ('default_max_items', '5')
    ]
    
    cursor.executemany('''
    INSERT INTO settings (key, value) VALUES (?, ?)
    ''', settings)

def main():
    # Get the database path in the project root
    db_path = os.path.join(os.path.dirname(__file__), 'game_data.db')
    
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Enable foreign key constraints
        cursor.execute('PRAGMA foreign_keys = ON')
        
        # Create tables if they don't exist
        create_tables(cursor)
        
        # Import the data
        import_levels_and_expressions(cursor)
        import_settings(cursor)
        
        # Commit the changes
        conn.commit()
        print("Veri başarıyla içe aktarıldı!")
        
    except sqlite3.Error as e:
        print(f"Veritabanı hatası: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    main()

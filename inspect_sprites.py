import sqlite3
from pathlib import Path

# Database path
base_dir = Path('.').absolute()
db_path = base_dir / 'game_data.db'

def inspect_sprites():
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("--- Sprites ---")
    cursor.execute("SELECT * FROM sprites")
    sprites = cursor.fetchall()
    for s in sprites:
        print(f"ID: {s['id']}, Name: {s['name']}, Path: {s['path']}")
        
    print("\n--- Level Backgrounds ---")
    cursor.execute("""
        SELECT l.level_number, l.level_name, s.name as sprite_name, s.path
        FROM levels l
        LEFT JOIN level_background_sprites lbs ON l.id = lbs.level_id
        LEFT JOIN sprites s ON lbs.sprite_id = s.id
        WHERE l.game_id = 1
        ORDER BY l.level_number
    """)
    rows = cursor.fetchall()
    for row in rows:
        print(f"Level {row['level_number']} ({row['level_name']}): {row['sprite_name']} ({row['path']})")
        
    conn.close()

if __name__ == "__main__":
    inspect_sprites()

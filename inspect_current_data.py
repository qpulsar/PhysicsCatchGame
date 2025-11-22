import sqlite3
import os
from pathlib import Path

# Database path
base_dir = Path('.').absolute()
db_path = base_dir / 'game_data.db'

def inspect_game():
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get Game
    cursor.execute("SELECT * FROM games WHERE name = 'Fiziksel Büyüklükler'")
    game = cursor.fetchone()
    
    if not game:
        print("Game not found!")
        return

    print(f"Game: {game['name']} (ID: {game['id']})")
    
    # Get Levels
    cursor.execute("SELECT * FROM levels WHERE game_id = ? ORDER BY level_number", (game['id'],))
    levels = cursor.fetchall()
    
    for level in levels:
        print(f"\nLevel {level['level_number']}: {level['level_name']}")
        print(f"  Current Desc: {level['level_description']}")
        print(f"  Current Speed: {level['item_speed']}")
        print(f"  Current Wrong %: {level['wrong_answer_percentage']}")
        
        # Get sample expressions to understand the topic
        cursor.execute("SELECT expression, is_correct FROM expressions WHERE level_id = ? LIMIT 5", (level['id'],))
        exprs = cursor.fetchall()
        print("  Sample Expressions:")
        for e in exprs:
            type_str = "Correct" if e['is_correct'] else "Wrong"
            print(f"    - {e['expression']} ({type_str})")

    conn.close()

def list_images():
    img_dir = base_dir / 'assets' / 'images'
    print(f"\nImage Assets in {img_dir}:")
    for root, dirs, files in os.walk(img_dir):
        for file in files:
            if not file.startswith('.'):
                rel_path = os.path.relpath(os.path.join(root, file), base_dir)
                print(rel_path)

if __name__ == "__main__":
    inspect_game()
    list_images()

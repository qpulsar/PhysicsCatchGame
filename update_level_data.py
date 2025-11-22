import sqlite3
from pathlib import Path

# Database path
base_dir = Path('.').absolute()
db_path = base_dir / 'game_data.db'

def update_game_data():
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("Updating game data...")
    
    # 1. Add Sprites (Backgrounds)
    backgrounds = [
        ("bg_level1", "assets/images/backgrounds/level1.jpg"),
        ("bg_level2", "assets/images/backgrounds/level2.jpg"),
        ("bg_level3", "assets/images/backgrounds/3.jpg"),
        ("bg_level4", "assets/images/backgrounds/4_800x600.jpg"),
    ]
    
    bg_ids = {}
    for name, path in backgrounds:
        # Check if exists
        cursor.execute("SELECT id FROM sprites WHERE path = ?", (path,))
        row = cursor.fetchone()
        if row:
            bg_ids[name] = row['id']
            print(f"Sprite {name} already exists (ID: {row['id']})")
        else:
            cursor.execute("INSERT INTO sprites (name, path) VALUES (?, ?)", (name, path))
            bg_ids[name] = cursor.lastrowid
            print(f"Added sprite {name} (ID: {cursor.lastrowid})")
            
    # 2. Update Levels
    levels_config = [
        {
            "number": 1,
            "desc": "Bu bölümde sadece TEMEL büyüklükleri (Kütle, Uzunluk, Zaman, Akım Şiddeti, Sıcaklık, Madde Miktarı, Işık Şiddeti) topla. Türetilmiş büyüklüklerden kaçın!",
            "speed": 2.0,
            "wrong_pct": 20,
            "max_items": 5,
            "bg_key": "bg_level1",
            "effect_correct": "assets/images/effects/preset_ring_fire.png",
            "effect_wrong": "assets/images/effects/preset_explosion_smoke.png"
        },
        {
            "number": 2,
            "desc": "Sırada TÜRETİLMİŞ büyüklükler var (Hız, İvme, Kuvvet, Enerji vb.). Temel büyüklüklere dokunma!",
            "speed": 2.5,
            "wrong_pct": 25,
            "max_items": 6,
            "bg_key": "bg_level2",
            "effect_correct": "assets/images/effects/preset_ring_blueish.png",
            "effect_wrong": "assets/images/effects/explosion_blueish_smoke.png"
        },
        {
            "number": 3,
            "desc": "Sadece SKALER (yönsüz) büyüklükleri topla (Kütle, Zaman, Enerji, Sıcaklık). Vektörel olanlardan uzak dur!",
            "speed": 3.0,
            "wrong_pct": 30,
            "max_items": 7,
            "bg_key": "bg_level3",
            "effect_correct": "assets/images/effects/ring_magic.png",
            "effect_wrong": "assets/images/effects/preset_explosion_smoke.png"
        },
        {
            "number": 4,
            "desc": "Dikkat! Sadece VEKTÖREL (yönlü) büyüklükleri yakala (Hız, Kuvvet, İvme, Yer Değiştirme). Skalerleri pas geç!",
            "speed": 3.5,
            "wrong_pct": 35,
            "max_items": 8,
            "bg_key": "bg_level4",
            "effect_correct": "assets/images/effects/preset_shockwave_fire.png",
            "effect_wrong": "assets/images/effects/preset_explosion_fire.png"
        }
    ]
    
    for cfg in levels_config:
        # Update level details
        print(f"Updating Level {cfg['number']}...")
        cursor.execute("""
            UPDATE levels 
            SET level_description = ?,
                item_speed = ?,
                wrong_answer_percentage = ?,
                max_items_on_screen = ?,
                effect_correct_sheet = ?,
                effect_wrong_sheet = ?
            WHERE game_id = 1 AND level_number = ?
        """, (
            cfg['desc'], 
            cfg['speed'], 
            cfg['wrong_pct'], 
            cfg['max_items'], 
            cfg['effect_correct'],
            cfg['effect_wrong'],
            cfg['number']
        ))
        
        # Get Level ID
        cursor.execute("SELECT id FROM levels WHERE game_id = 1 AND level_number = ?", (cfg['number'],))
        lvl_row = cursor.fetchone()
        if lvl_row:
            lvl_id = lvl_row['id']
            
            # Update Background
            bg_id = bg_ids.get(cfg['bg_key'])
            if bg_id:
                # Clear old background mapping
                cursor.execute("DELETE FROM level_background_sprites WHERE level_id = ?", (lvl_id,))
                # Add new mapping
                cursor.execute("INSERT INTO level_background_sprites (level_id, sprite_id) VALUES (?, ?)", (lvl_id, bg_id))
                print(f"  -> Assigned background {cfg['bg_key']} (ID: {bg_id})")
            else:
                print(f"  -> Background {cfg['bg_key']} not found in sprite map!")
        else:
            print(f"  -> Level {cfg['number']} not found!")
            
    # 3. Update Music Setting
    print("Updating Music Settings...")
    cursor.execute("""
        INSERT OR REPLACE INTO game_settings (game_id, key, value, updated_at)
        VALUES (1, 'background_music', 'assets/audio/music/town.mp3', CURRENT_TIMESTAMP)
    """)
    
    conn.commit()
    conn.close()
    print("Done!")

if __name__ == "__main__":
    update_game_data()

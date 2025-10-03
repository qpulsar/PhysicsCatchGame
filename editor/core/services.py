"""Core services for the game editor."""
from typing import Dict, List, Optional, Any
from datetime import datetime
import os
import shutil
import unicodedata

from .models import Game, Level, Expression, GameSettings, Sprite, SpriteDefinition, Screen
from ..database.database import DatabaseManager


class GameService:
    """Service for game-related operations."""
    
    def __init__(self, db_manager: DatabaseManager):
        """Initialize with a database manager."""
        self.db = db_manager
    
    def create_game(self, name: str, description: str = "") -> Game:
        """Create a new game and return the Game object."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO games (name, description, created_at, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)',
                (name, description)
            )
            conn.commit()
            game_id = cursor.lastrowid
            cursor.execute('SELECT * FROM games WHERE id = ?', (game_id,))
            row = cursor.fetchone()
            return Game.from_dict(dict(row))
    
    def get_games(self) -> list:
        """Get all games as Game objects."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM games ORDER BY name')
            return [Game.from_dict(dict(row)) for row in cursor.fetchall()]
    
    def get_game(self, game_id: int = 1) -> Optional[Game]:
        """Get a game by ID."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM games WHERE id = ?', (game_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return Game.from_dict(dict(row))

    def update_game(self, game_id: int, name: str, description: str) -> Optional[Game]:
        """Update a game's name and description."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE games SET name = ?, description = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                (name, description, game_id)
            )
            conn.commit()
            if cursor.rowcount == 0:
                return None
        return self.get_game(game_id)

    def delete_game(self, game_id: int) -> bool:
        """Delete a game and all its related data."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            # Note: Ensure foreign keys are set up with ON DELETE CASCADE in the DB schema
            # or delete related data manually here.
            cursor.execute('DELETE FROM games WHERE id = ?', (game_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_settings(self, game_id: int = 1) -> GameSettings:
        """Get game settings for the given game_id."""
        settings: Dict[str, str] = {}
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT key, value FROM game_settings 
                WHERE game_id = ?
            ''', (game_id,))
            for key, value in cursor.fetchall():
                settings[key] = value
        return GameSettings(game_id=game_id, settings=settings)

    def update_setting(self, game_id: int, key: str, value: str) -> None:
        """Update a single game setting key/value."""
        self.db.set_setting(game_id, key, value)


class ScreenService:
    """Service for editor-designed screens stored in the database.

    Provides CRUD helpers around `screens` table to manage JSON-based screen layouts
    such as the Opening screen. Use this from editor UI and runtime loaders.
    """

    def __init__(self, db_manager: DatabaseManager):
        """Initialize with a database manager."""
        self.db = db_manager

    def upsert_screen(self, game_id: int, name: str, type_: str, data_json: str) -> Screen:
        """Insert or update a screen configuration and return the Screen model."""
        sid = self.db.upsert_screen(game_id, name, type_, data_json)
        row = self.db.get_screen(game_id, name)
        return Screen.from_dict(dict(row)) if row else Screen(id=sid, game_id=game_id, name=name, type=type_, data_json=data_json)

    def get_screen(self, game_id: int, name: str) -> Optional[Screen]:
        """Fetch a screen by game and name."""
        row = self.db.get_screen(game_id, name)
        return Screen.from_dict(dict(row)) if row else None

    def list_screens(self, game_id: int) -> List[Screen]:
        """List all screens for a game."""
        rows = self.db.list_screens(game_id)
        return [Screen.from_dict(dict(r)) for r in rows]

    def delete_screen(self, game_id: int, name: str) -> bool:
        """Delete a screen by name for a game."""
        return self.db.delete_screen(game_id, name)
    
    def get_settings(self, game_id: int = 1) -> GameSettings:
        """Get game settings."""
        settings = {}
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT key, value FROM game_settings 
                WHERE game_id = ?
            ''', (game_id,))
            for key, value in cursor.fetchall():
                settings[key] = value
        
        return GameSettings(game_id=game_id, settings=settings)
    
    def update_setting(self, game_id: int, key: str, value: str) -> None:
        """Update a game setting."""
        self.db.set_setting(game_id, key, value)


class LevelService:
    """Service for level-related operations."""
    
    def __init__(self, db_manager: DatabaseManager):
        """Initialize with a database manager."""
        self.db = db_manager
    
    def get_levels(self, game_id: int = 1) -> List[Level]:
        """Get all levels for a game."""
        rows = self.db.get_levels(game_id)
        return [Level.from_dict(dict(row)) for row in rows]
    
    def get_level(self, level_id: int) -> Optional[Level]:
        """Get a level by ID."""
        row = self.db.get_level(level_id)
        if not row:
            return None
        return Level.from_dict(dict(row))
    
    def create_level(self, level_data: Dict[str, Any]) -> Level:
        """Create a new level."""
        level_id = self.db.add_level(level_data)
        return self.get_level(level_id)
    
    def update_level(self, level_id: int, level_data: Dict[str, Any]) -> Optional[Level]:
        """Update an existing level."""
        success = self.db.update_level(level_id, level_data)
        if not success:
            return None
        return self.get_level(level_id)
    
    def delete_level(self, level_id: int) -> bool:
        """Delete a level by ID."""
        return self.db.delete_level(level_id)

    def get_level_background_sprite_ids(self, level_id: int) -> List[int]:
        """Belirtilen seviye için arka plan sprite ID'lerini döndürür.

        Bu metod, seviye ekranında yukarıdan düşen ifadeler için kullanılacak
        arka plan sprite'larını yönetmek amacıyla kullanılır.
        """
        return self.db.get_level_background_sprite_ids(level_id)

    def set_level_background_sprite_ids(self, level_id: int, sprite_ids: List[int]) -> None:
        """Belirtilen seviye için arka plan sprite ID'lerini atomik olarak günceller.

        Var olan eşleştirmeler silinir ve verilen liste eklenir.
        """
        self.db.set_level_background_sprite_ids(level_id, sprite_ids)

    def get_level_background_region_ids(self, level_id: int) -> List[int]:
        """Belirtilen seviye için seçili sprite bölge (region) ID'lerini döndürür."""
        return self.db.get_level_background_region_ids(level_id)

    def set_level_background_region_ids(self, level_id: int, region_ids: List[int]) -> None:
        """Belirtilen seviye için sprite bölge (region) seçimlerini atomik olarak günceller."""
        self.db.set_level_background_region_ids(level_id, region_ids)


class ExpressionService:
    """Service for expression-related operations."""
    
    def __init__(self, db_manager: DatabaseManager):
        """Initialize with a database manager."""
        self.db = db_manager
    
    def get_expressions(self, level_id: int) -> List[Expression]:
        """Get all expressions for a level."""
        rows = self.db.get_expressions(level_id)
        return [Expression.from_dict(dict(row)) for row in rows]
    
    def add_expression(self, level_id: int, expression: str, is_correct: bool) -> Expression:
        """Add a new expression."""
        expr_id = self.db.add_expression(level_id, expression, is_correct)
        return self._get_expression(expr_id)
    
    def update_expression(self, expr_id: int, expression: str, is_correct: bool) -> Optional[Expression]:
        """Update an existing expression."""
        success = self.db.update_expression(expr_id, expression, is_correct)
        if not success:
            return None
        return self._get_expression(expr_id)
    
    def delete_expression(self, expr_id: int) -> bool:
        """Delete an expression by ID."""
        return self.db.delete_expression(expr_id)
    
    def _get_expression(self, expr_id: int) -> Optional[Expression]:
        """Get an expression by ID."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM expressions WHERE id = ?', (expr_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return Expression.from_dict(dict(row))


class SpriteService:
    """Service for sprite-related operations."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def add_sprite_sheet(self, name: str, path: str) -> Sprite:
        """Add a new sprite sheet to the GLOBAL pool.

        Copies the file under `assets/sprites/` and stores an entry in `sprites` table.
        """
        # Copy into global assets directory
        dst_dir = os.path.join('assets', 'sprites')
        os.makedirs(dst_dir, exist_ok=True)
        basename = os.path.basename(path)
        safe_name = self._sanitize_filename(basename)
        dst_path = self._avoid_collision(dst_dir, safe_name)
        if os.path.abspath(path) != os.path.abspath(dst_path):
            shutil.copy2(path, dst_path)
        rel_dst_path = dst_path.replace('\\', '/')

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO sprites (name, path) VALUES (?, ?)',
                (safe_name, rel_dst_path)
            )
            conn.commit()
            sprite_id = cursor.lastrowid
            return self.get_sprite_sheet(sprite_id)

    def _sanitize_filename(self, name: str) -> str:
        name = name.strip().lower()
        name = unicodedata.normalize('NFKD', name)
        name = name.encode('ascii', 'ignore').decode('ascii')
        base, ext = os.path.splitext(name)
        safe_base = ''.join(c if c.isalnum() or c in ('-', '_') else '_' for c in base)
        safe_ext = ''.join(c if c.isalnum() else '' for c in ext)
        ext = ('.' + safe_ext) if safe_ext else ''
        if not safe_base:
            safe_base = 'file'
        return safe_base + ext

    def _avoid_collision(self, directory: str, filename: str) -> str:
        base, ext = os.path.splitext(filename)
        candidate = os.path.join(directory, filename)
        counter = 1
        while os.path.exists(candidate):
            candidate = os.path.join(directory, f"{base}_{counter}{ext}")
            counter += 1
        return candidate

    def get_sprite_sheets(self) -> List[Sprite]:
        """Get all sprite sheets from the GLOBAL pool."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM sprites ORDER BY name')
            return [Sprite.from_dict(dict(row)) for row in cursor.fetchall()]

    def get_sprite_sheet(self, sprite_id: int) -> Optional[Sprite]:
        """Gets a single sprite sheet by its ID."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM sprites WHERE id = ?', (sprite_id,))
            row = cursor.fetchone()
            return Sprite.from_dict(dict(row)) if row else None

    def delete_sprite_sheet(self, sprite_id: int) -> bool:
        """Deletes a sprite sheet and its definitions."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM sprites WHERE id = ?', (sprite_id,))
            conn.commit()
            return cursor.rowcount > 0

    def add_or_update_sprite_definition(self, sprite_id: int, expression_id: int, coords: Dict[str, int]) -> SpriteDefinition:
        """Creates or updates a sprite definition for an expression."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                INSERT INTO sprite_definitions (sprite_id, expression_id, x, y, width, height)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(expression_id) DO UPDATE SET
                    sprite_id = excluded.sprite_id,
                    x = excluded.x,
                    y = excluded.y,
                    width = excluded.width,
                    height = excluded.height
                ''',
                (sprite_id, expression_id, coords['x'], coords['y'], coords['width'], coords['height'])
            )
            conn.commit()
            # We need to fetch the ID of the inserted/updated row
            cursor.execute('SELECT * FROM sprite_definitions WHERE expression_id = ?', (expression_id,))
            row = cursor.fetchone()
            return SpriteDefinition.from_dict(dict(row))
            
    def get_sprite_definition_for_expr(self, expression_id: int) -> Optional[SpriteDefinition]:
        """Gets the sprite definition for a specific expression."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM sprite_definitions WHERE expression_id = ?', (expression_id,))
            row = cursor.fetchone()
            return SpriteDefinition.from_dict(dict(row)) if row else None
            
    def get_all_definitions_for_sheet(self, sprite_id: int) -> List[SpriteDefinition]:
        """Gets all sprite definitions associated with a sprite sheet."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM sprite_definitions WHERE sprite_id = ?', (sprite_id,))
            return [SpriteDefinition.from_dict(dict(row)) for row in cursor.fetchall()]

    def remove_sprite_definition(self, expression_id: int) -> bool:
        """Removes a sprite definition linked to an expression."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM sprite_definitions WHERE expression_id = ?', (expression_id,))
            conn.commit()
            return cursor.rowcount > 0

    # -------- Sprite Regions (DB-backed) --------
    def list_sprite_regions(self) -> List[Dict[str, Any]]:
        """List all saved sprite regions.

        Returns a list of dicts: {id, image_path, name, x, y, width, height}.
        """
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, image_path, name, x, y, width, height
                FROM sprite_regions
                ORDER BY image_path, name
            ''')
            return [dict(row) for row in cursor.fetchall()]

    def upsert_sprite_region(self, image_path: str, name: str, coords: Dict[str, int]) -> Dict[str, Any]:
        """Create or update a sprite region by unique (image_path, name)."""
        # normalize path to a project-root-relative forward-slash path
        image_path = self._normalize_image_path(image_path)
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO sprite_regions (image_path, name, x, y, width, height)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(image_path, name) DO UPDATE SET
                    x = excluded.x,
                    y = excluded.y,
                    width = excluded.width,
                    height = excluded.height
            ''', (image_path, name, int(coords['x']), int(coords['y']), int(coords['width']), int(coords['height'])))
            conn.commit()
            cursor.execute('''
                SELECT id, image_path, name, x, y, width, height
                FROM sprite_regions WHERE image_path = ? AND name = ?
            ''', (image_path, name))
            row = cursor.fetchone()
            return dict(row) if row else {}

    def rename_sprite_region(self, image_path: str, old_name: str, new_name: str) -> bool:
        """Rename a sprite region. Returns True if a row was updated."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE sprite_regions
                SET name = ?
                WHERE image_path = ? AND name = ?
            ''', (new_name, image_path, old_name))
            conn.commit()
            return cursor.rowcount > 0

    def delete_sprite_region(self, image_path: str, name: str) -> bool:
        """Delete a sprite region by key."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM sprite_regions WHERE image_path = ? AND name = ?', (image_path, name))
            conn.commit()
            return cursor.rowcount > 0




    # ---- Helpers ----
    def _normalize_image_path(self, image_path: str) -> str:
        """Return a normalized, project-root-relative path with forward slashes.

        - Converts absolute paths under project root to relative
        - Ensures consistent forward slashes
        - Leaves other paths as-is
        """
        if not image_path:
            return image_path
        p = image_path.replace('\\', '/').strip()
        # If absolute and under project root, make relative
        try:
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
            if os.path.isabs(p):
                # normalize for os
                pr = project_root
                if p.startswith(pr):
                    rel = os.path.relpath(p, pr).replace('\\', '/')
                    return rel
        except Exception:
            pass
        # already relative
        return p

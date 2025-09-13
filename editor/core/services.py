"""Core services for the game editor."""
from typing import Dict, List, Optional, Any
from datetime import datetime

from .models import Game, Level, Expression, GameSettings, Sprite, SpriteDefinition
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

    def add_sprite_sheet(self, game_id: int, name: str, path: str) -> Sprite:
        """Adds a new sprite sheet to the database."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO sprites (game_id, name, path) VALUES (?, ?, ?)',
                (game_id, name, path)
            )
            conn.commit()
            sprite_id = cursor.lastrowid
            return self.get_sprite_sheet(sprite_id)

    def get_sprite_sheets(self, game_id: int) -> List[Sprite]:
        """Gets all sprite sheets for a game."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM sprites WHERE game_id = ? ORDER BY name', (game_id,))
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

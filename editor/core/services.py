"""Core services for the game editor."""
from typing import Dict, List, Optional, Any
from datetime import datetime

from .models import Game, Level, Expression, GameSettings
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

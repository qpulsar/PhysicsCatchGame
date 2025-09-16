"""Database module for the game editor."""
import os
import sqlite3
from typing import Any, Dict, List, Optional, Tuple, Union
from pathlib import Path


class DatabaseManager:
    """Manages database connections and operations."""
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize the database manager.
        
        Args:
            db_path: Path to the SQLite database file. If None, uses default location.
        """
        if db_path is None:
            base_dir = Path(__file__).parent.parent.parent
            self.db_path = str(base_dir / 'game_data.db')
        else:
            self.db_path = db_path
        
        self._initialize_database()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _initialize_database(self) -> None:
        """Initialize the database with required tables and default data."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Enable foreign key support
            cursor.execute('PRAGMA foreign_keys = ON')
            
            # Create tables
            self._create_tables(cursor)
            
            # Initialize default data
            self._initialize_default_data(cursor)
            
            conn.commit()
    
    def _create_tables(self, cursor: sqlite3.Cursor) -> None:
        """Create database tables if they don't exist."""
        # Create games table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Create levels table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS levels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER NOT NULL,
            level_number INTEGER NOT NULL,
            level_name TEXT NOT NULL,
            level_description TEXT,
            wrong_answer_percentage INTEGER NOT NULL 
                CHECK(wrong_answer_percentage >= 0 AND wrong_answer_percentage <= 100),
            item_speed REAL NOT NULL CHECK(item_speed > 0),
            max_items_on_screen INTEGER NOT NULL CHECK(max_items_on_screen > 0),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (game_id) REFERENCES games (id) ON DELETE CASCADE,
            UNIQUE (game_id, level_number)
        )''')
        
        # Create expressions table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS expressions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level_id INTEGER NOT NULL,
            expression TEXT NOT NULL,
            is_correct BOOLEAN NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (level_id) REFERENCES levels (id) ON DELETE CASCADE
        )''')
        
        # Create game_settings table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS game_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (game_id) REFERENCES games (id) ON DELETE CASCADE,
            UNIQUE (game_id, key)
        )''')

        # Create sprites table to store sprite sheets
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS sprites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            path TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        # Create sprite_definitions table to store individual sprite coordinates
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS sprite_definitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sprite_id INTEGER NOT NULL,
            expression_id INTEGER NOT NULL UNIQUE,
            x INTEGER NOT NULL,
            y INTEGER NOT NULL,
            width INTEGER NOT NULL,
            height INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sprite_id) REFERENCES sprites (id) ON DELETE CASCADE,
            FOREIGN KEY (expression_id) REFERENCES expressions (id) ON DELETE CASCADE
        )''')

        # Create sprite_regions table to store user-defined regions on image assets
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS sprite_regions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_path TEXT NOT NULL,
            name TEXT NOT NULL,
            x INTEGER NOT NULL,
            y INTEGER NOT NULL,
            width INTEGER NOT NULL,
            height INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (image_path, name)
        )''')
        
        # Create screens table to store screen layouts as JSON per game
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS screens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            data_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (game_id) REFERENCES games (id) ON DELETE CASCADE,
            UNIQUE (game_id, name)
        )''')
    
    def _initialize_default_data(self, cursor: sqlite3.Cursor) -> None:
        """Initialize default game and settings."""
        # Create default game if not exists
        cursor.execute('''
        INSERT OR IGNORE INTO games (id, name, description) 
        VALUES (1, 'Fiziksel Büyüklükler', 'Temel fiziksel büyüklükler oyunu')
        ''')
        
        # Initialize default settings for the default game
        default_settings = [
            (1, 'total_levels', '10'),
            (1, 'default_wrong_percentage', '20'),
            (1, 'default_item_speed', '2.0'),
            (1, 'default_max_items', '5')
        ]
        
        cursor.executemany('''
        INSERT OR IGNORE INTO game_settings (game_id, key, value)
        VALUES (?, ?, ?)
        ''', default_settings)
    
    # Level operations
    def get_levels(self, game_id: int = 1) -> List[sqlite3.Row]:
        """Get all levels for a game."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM levels 
                WHERE game_id = ? 
                ORDER BY level_number
            ''', (game_id,))
            return cursor.fetchall()
    
    def get_level(self, level_id: int) -> Optional[sqlite3.Row]:
        """Get a level by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM levels WHERE id = ?', (level_id,))
            return cursor.fetchone()
    
    def add_level(self, level_data: Dict[str, Any]) -> int:
        """Add a new level."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO levels (
                    game_id, level_number, level_name, level_description,
                    wrong_answer_percentage, item_speed, max_items_on_screen
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                level_data.get('game_id', 1),
                level_data['level_number'],
                level_data['level_name'],
                level_data.get('level_description', ''),
                level_data.get('wrong_answer_percentage', 20),
                level_data.get('item_speed', 2.0),
                level_data.get('max_items_on_screen', 5)
            ))
            conn.commit()
            return cursor.lastrowid
    
    def update_level(self, level_id: int, level_data: Dict[str, Any]) -> bool:
        """Update an existing level."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE levels 
                SET level_number = ?,
                    level_name = ?,
                    level_description = ?,
                    wrong_answer_percentage = ?,
                    item_speed = ?,
                    max_items_on_screen = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (
                level_data['level_number'],
                level_data['level_name'],
                level_data.get('level_description', ''),
                level_data.get('wrong_answer_percentage', 20),
                level_data.get('item_speed', 2.0),
                level_data.get('max_items_on_screen', 5),
                level_id
            ))
            conn.commit()
            return cursor.rowcount > 0
    
    def delete_level(self, level_id: int) -> bool:
        """Delete a level by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM levels WHERE id = ?', (level_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    # Expression operations
    def get_expressions(self, level_id: int) -> List[sqlite3.Row]:
        """Get all expressions for a level."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM expressions 
                WHERE level_id = ?
                ORDER BY id
            ''', (level_id,))
            return cursor.fetchall()
    
    def add_expression(self, level_id: int, expression: str, is_correct: bool) -> int:
        """Add a new expression."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO expressions (level_id, expression, is_correct)
                VALUES (?, ?, ?)
            ''', (level_id, expression, is_correct))
            conn.commit()
            return cursor.lastrowid
    
    def update_expression(self, expr_id: int, expression: str, is_correct: bool) -> bool:
        """Update an existing expression."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE expressions 
                SET expression = ?,
                    is_correct = ?
                WHERE id = ?
            ''', (expression, is_correct, expr_id))
            conn.commit()
            return cursor.rowcount > 0
    
    def delete_expression(self, expr_id: int) -> bool:
        """Delete an expression by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM expressions WHERE id = ?', (expr_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    # Settings operations
    def get_setting(self, game_id: int, key: str) -> Optional[str]:
        """Get a game setting by key."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT value FROM game_settings 
                WHERE game_id = ? AND key = ?
            ''', (game_id, key))
            result = cursor.fetchone()
            return result[0] if result else None
    
    def set_setting(self, game_id: int, key: str, value: str) -> None:
        """Set a game setting."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO game_settings 
                (game_id, key, value, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ''', (game_id, key, value))
            conn.commit()

    # Screens operations
    def upsert_screen(self, game_id: int, name: str, type_: str, data_json: str) -> int:
        """Create or update a screen for a game.

        Returns the screen id.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO screens (game_id, name, type, data_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(game_id, name) DO UPDATE SET
                    type = excluded.type,
                    data_json = excluded.data_json,
                    updated_at = CURRENT_TIMESTAMP
            ''', (game_id, name, type_, data_json))
            conn.commit()
            # fetch id
            cursor.execute('SELECT id FROM screens WHERE game_id = ? AND name = ?', (game_id, name))
            row = cursor.fetchone()
            return int(row['id']) if row else 0

    def get_screen(self, game_id: int, name: str) -> Optional[sqlite3.Row]:
        """Get a screen row by game_id and name."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM screens WHERE game_id = ? AND name = ?', (game_id, name))
            return cursor.fetchone()

    def list_screens(self, game_id: int) -> List[sqlite3.Row]:
        """List all screens for a given game."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM screens WHERE game_id = ? ORDER BY name', (game_id,))
            return cursor.fetchall()

    def delete_screen(self, game_id: int, name: str) -> bool:
        """Delete a screen by game_id and name."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM screens WHERE game_id = ? AND name = ?', (game_id, name))
            conn.commit()
            return cursor.rowcount > 0

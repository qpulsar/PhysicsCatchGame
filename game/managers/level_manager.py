"""Level Manager Module

This module provides the LevelManager class which handles level progression,
item spawning, and level completion logic for the game.

Runtime integration notes:
- Reads per-game settings from the `game_settings` table using the runtime
  `Database` helper (no editor dependency) to configure:
    * default_wrong_percentage (0-100)
    * default_item_speed (float)
    * default_max_items (int)
- These settings are optional; sensible defaults are used when missing.
"""

import random
import pygame
import sqlite3
from typing import Dict, List, Optional, Tuple

from settings import *
from ..screens.game_screens import Database  # reuse simple runtime DB helper
from ..core.utils import get_resource_path

# This is a simplified version of the DatabaseManager from the editor
# to avoid complex dependencies.
class LevelDatabase:
    def __init__(self, db_path='game_data.db'):
        self.db_path = db_path

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_level_data(self, game_id: int, level_number: int) -> Optional[sqlite3.Row]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM levels WHERE game_id = ? AND level_number = ?',
                (game_id, level_number)
            )
            return cursor.fetchone()

    def get_game_settings(self, game_id: int) -> Dict[str, str]:
        """Oyunun genel ayarlarını (varsayılan hız, oran vb.) döndürür."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT key, value FROM game_settings WHERE game_id = ?', (game_id,))
                return {row[0]: row[1] for row in cursor.fetchall()}
        except Exception:
            return {}

    def get_expressions_for_level(self, level_id: int) -> List[sqlite3.Row]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM expressions WHERE level_id = ?', (level_id,))
            return cursor.fetchall()

class LevelManager:
    """Manages game levels, item spawning, and level progression.
    
    This class handles:
    - Level setup and initialization
    - Item spawning logic
    - Level completion tracking
    - Management of correct and incorrect items
    
    Class Attributes:
        LEVEL_TARGETS: List of target categories for each level.
        
    Instance Attributes:
        level: Current level number.
        target_category: The current target category for the level.
        correct_items: List of correct items for the current level.
        dropped_correct: List of correct items that have been dropped.
        caught_correct: List of correct items that have been caught.
        available_quantities: Dictionary of available quantities for each category.
        spawn_events: List of scheduled spawn events.
        spawn_index: Index of the next spawn event.
        item_spawned_count: Number of items spawned so far.
        total_items_to_spawn: Total items to spawn in the level.
        spawn_ready: Whether the spawner is ready to start.
    """
    
    # Define target categories for each level (1-based index)
    LEVEL_TARGETS = [
        'Temel Büyüklükler',  # Level 1
        'Türetilmiş Büyüklükler',  # Level 2
        'Skaler Büyüklükler',  # Level 3
        'Vektörel Büyüklükler',  # Level 4
        'Temel Büyüklükler'  # Level 5 (repeat or add more as needed)
    ]
    
    def __init__(self):
        """Initialize a new LevelManager with default values.

        Doc:
            - Initializes internal queues and default gameplay parameters.
            - Item speed and other parameters may be overridden by game settings
              when `setup_level()` is called.
        """
        # Seviye veri tabanını bundle-safe yolla başlat
        self.db = LevelDatabase(get_resource_path('game_data.db'))
        self.level: int = 1
        self.game_id: Optional[int] = None
        self.target_category: Optional[str] = None # Will be based on level description or a new DB field
        self.correct_items: List[str] = []
        self.wrong_items: List[str] = []
        self.dropped_correct: List[str] = []
        self.caught_correct: List[str] = []
        self.level_queue: List[str] = []
        self.spawn_events: List[dict] = []
        self.spawn_index: int = 0
        self.item_spawned_count: int = 0
        self.total_items_to_spawn: int = 0
        self.spawn_ready: bool = False
        # Gameplay parameters (overridable via settings)
        self.item_speed: float = 3.0
        self.max_items_on_screen: int = 5
        self.wrong_answer_percentage: int = 40
    
    def setup_level(self, level_number: int, game_id: int) -> bool:
        """Belirtilen numara ile yeni bir seviye kurulumu yapar.

        Doc:
            - DB'den seviye satırını ve ifadeleri (expressions) yükler.
            - Seviye tablosundaki `item_speed`, `wrong_answer_percentage` ve
              `max_items_on_screen` değerlerini uygular.
            - Bu değerler artık global ayarlarla ezilmez, tasarım ekranındaki değerler esastır.

        Args:
            level_number: Kurulacak seviye numarası.
            game_id: Aktif oyun id'si.

        Returns:
            bool: Seviye başarıyla yüklendiyse True.
        """
        level_data = self.db.get_level_data(game_id, level_number)
        if not level_data:
            print(f"Level {level_number} for game {game_id} not found in database.")
            return False

        self.level = level_number
        self.game_id = game_id

        level_id = level_data['id']
        self.target_category = level_data['level_name'] # Using level name as target for now
        
        all_expressions = self.db.get_expressions_for_level(level_id)
        self.correct_items = [e['expression'] for e in all_expressions if e['is_correct']]
        self.wrong_items = [e['expression'] for e in all_expressions if not e['is_correct']]

        self.dropped_correct = []
        self.caught_correct = []
        self.level_queue = self.correct_items.copy()
        
        # Reset spawn state
        self.spawn_events = []
        self.spawn_index = 0
        self.item_spawned_count = 0
        self.total_items_to_spawn = 0
        self.spawn_ready = False
        
        # ----------------------------------------------------------------------
        # Seviye ayarlarını uygula: Level-specific > Game Default > Hardcoded
        # ----------------------------------------------------------------------
        try:
            gs = self.db.get_game_settings(game_id)
            
            def _get_f(row, key, gs_key, default):
                if key in row.keys() and row[key] is not None: return float(row[key])
                return float(gs.get(gs_key) or default)
                
            def _get_i(row, key, gs_key, default):
                if key in row.keys() and row[key] is not None: return int(row[key])
                return int(gs.get(gs_key) or default)

            self.item_speed = _get_f(level_data, 'item_speed', 'default_item_speed', 3.0)
            self.max_items_on_screen = _get_i(level_data, 'max_items_on_screen', 'default_max_items', 5)
            self.wrong_answer_percentage = _get_i(level_data, 'wrong_answer_percentage', 'default_wrong_percentage', 40)
            
            # Sınır kontrolleri
            self.item_speed = max(0.1, self.item_speed)
            self.max_items_on_screen = max(1, self.max_items_on_screen)
            self.wrong_answer_percentage = max(0, min(100, self.wrong_answer_percentage))
            
            print(f"[LevelManager] Setup Level {level_number}: Speed={self.item_speed}, "
                  f"Wrong%={self.wrong_answer_percentage}, MaxItems={self.max_items_on_screen}")
            return True

        except Exception as e:
            print(f"[LevelManager] Error loading level settings: {e}. Using hardcoded defaults.")
            self.item_speed = 3.0
            self.max_items_on_screen = 5
            self.wrong_answer_percentage = 40
            return True
    
    def get_new_item(self) -> Tuple[str, str]:
        """Get a new item for the current level.

        Doc:
            - Chooses correct vs wrong based on `wrong_answer_percentage`.
            - Prioritizes remaining (not yet caught) correct items.

        Returns:
            tuple[str, str]: (item_text, item_category)
        """
        # Chance for correct item = 1 - wrong_percentage
        wrong_p = max(0.0, min(1.0, (self.wrong_answer_percentage or 0) / 100.0))
        correct_pick = random.random() > wrong_p
        if correct_pick and self.correct_items:
            # Check for items that still need to be spawned/caught
            remaining_correct = [item for item in self.correct_items if item not in self.caught_correct]
            if remaining_correct:
                 return random.choice(remaining_correct), self.target_category

        if self.wrong_items:
            return random.choice(self.wrong_items), "wrong" # Category for wrong items
        
        # Fallback to a correct item if no wrong items or if the random check failed but we must spawn something
        if self.correct_items:
            return random.choice(self.correct_items), self.target_category
        
        # Should not happen if a level has expressions
        return "BOŞ", "wrong"
    
    def prepare_spawn_events(self, min_items: int = 3, max_items: int = 6) -> None:
        """Gelecek nesne doğumlarını (spawn events) planlar.
        
        Batch sürecinde get_new_item() kullanarak wrong_answer_percentage oranına sadık kalır.
        """
        self.spawn_events = []
        current_time = pygame.time.get_ticks()
        
        count = random.randint(min_items, max_items)
        for _ in range(count):
            # Nesneler arası rastgele gecikme
            delay = random.randint(600, 1500)
            current_time += delay
            
            # get_new_item() hem doğru hem yanlış nesneleri oranına göre döner
            item_text, category = self.get_new_item()
            
            self.spawn_events.append({
                'time': current_time,
                'item_text': item_text,
                'category': category
            })
            
            # Doğru nesne ise takip listesine ekle
            if category == self.target_category:
                if item_text not in self.dropped_correct:
                    self.dropped_correct.append(item_text)
                    
        self.spawn_index = 0
        self.item_spawned_count = 0
        self.spawn_ready = True
    
    def should_spawn_item(self, current_time: int) -> Tuple[bool, Optional[str], Optional[str]]:
        """Check if a new item should be spawned based on the current time.
        
        Args:
            current_time: The current game time in milliseconds.
            
        Returns:
            A tuple containing:
            - bool: Whether an item should be spawned
            - str or None: The item text if spawning, else None
            - str or None: The item category if spawning, else None
        """
        if not self.spawn_ready or self.spawn_index >= len(self.spawn_events):
            return False, None, None
        
        next_event = self.spawn_events[self.spawn_index]
        if current_time >= next_event['time']:
            self.spawn_index += 1
            self.item_spawned_count += 1
            return True, next_event['item_text'], next_event['category']
        
        return False, None, None
    
    def is_level_complete(self) -> bool:
        """Check if the current level is complete.
        
        Returns:
            bool: True if all correct items have been caught, False otherwise.
        """
        return set(self.caught_correct) >= set(self.correct_items)
    
    def get_remaining_items(self) -> List[str]:
        """Get items that haven't been caught yet.
        
        Returns:
            List of item texts that are in the correct items but not yet caught.
        """
        return [item for item in self.correct_items if item not in self.caught_correct]
    
    def mark_item_caught(self, item_text: str) -> None:
        """Mark an item as caught.
        
        Args:
            item_text: The text of the item that was caught.
            
        Note:
            Only marks the item as caught if it's a correct item that hasn't
            been caught yet.
        """
        if item_text in self.correct_items and item_text not in self.caught_correct:
            self.caught_correct.append(item_text)

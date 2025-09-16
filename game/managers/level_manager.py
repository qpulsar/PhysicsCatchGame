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
        self.db = LevelDatabase()
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
    
    def setup_level(self, level_number: int, game_id: int):
        """Set up a new level with the given level number.

        Doc:
            - Loads level rows and expressions from the DB.
            - Reads game-level defaults from `game_settings` and applies them to
              internal parameters such as item speed and wrong percentage.

        Args:
            level_number: The level number to set up.
            game_id: Active game id.

        Raises:
            KeyError: If the level number is invalid.
        """
        self.level = level_number
        self.game_id = game_id

        level_data = self.db.get_level_data(game_id, level_number)
        if not level_data:
            print(f"Error: Level {level_number} for game {game_id} not found in database.")
            # Handle this case, e.g., by ending the game or loading a default.
            return

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
        
        print(f"Level {level_number} for Game {game_id} setup complete. Target: {self.target_category}")

        # Apply per-game settings (optional, with fallbacks)
        try:
            settings_map = Database().get_game_settings(game_id) or {}
            # parse with safe fallbacks
            self.item_speed = float(settings_map.get('default_item_speed', 3.0))
            # Bound speed to a sane range
            if self.item_speed <= 0:
                self.item_speed = 3.0
            self.max_items_on_screen = int(settings_map.get('default_max_items', 5))
            if self.max_items_on_screen < 1:
                self.max_items_on_screen = 5
            self.wrong_answer_percentage = int(settings_map.get('default_wrong_percentage', 40))
            self.wrong_answer_percentage = max(0, min(100, self.wrong_answer_percentage))
        except Exception as _:
            # keep defaults
            pass
    
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
        """Prepare the spawn events for the current level.

        Doc:
            - Ensures remaining correct items are included.
            - Adds additional items up to a random count between given bounds.
            - Spacing between spawns is randomized.

        Args:
            min_items: Minimum number of items to spawn additionally.
            max_items: Maximum number of items to spawn additionally.
        """
        print("\n=== Preparing Spawn Events ===")
        print(f"Target category: {self.target_category}")
        print(f"Correct items: {self.correct_items}")
        print(f"Caught correct: {self.caught_correct}")
        print(f"Dropped correct: {self.dropped_correct}")
        
        # Always spawn at least the remaining correct items
        remaining_correct = [
            item for item in self.correct_items 
            if item not in self.caught_correct and item not in self.dropped_correct
        ]
        
        # Calculate how many additional items to spawn (if any)
        additional_items = max(0, random.randint(min_items, max_items) - len(remaining_correct))
        total_items = len(remaining_correct) + additional_items
        
        print(f"Will spawn {total_items} items ({len(remaining_correct)} remaining correct + {additional_items} random)")
        
        self.spawn_events = []
        current_time = pygame.time.get_ticks()
        print(f"Current time: {current_time}")
        
        # First, handle items that need to be respawned from level_queue
        for item_text in self.level_queue[:]:  # Use a copy to safely modify the original
            delay = random.randint(400, 1200) if self.spawn_events else 0
            current_time += delay
            
            self.spawn_events.append({
                'time': current_time,
                'item_text': item_text,
                'category': self.target_category
            })
            print(f"  - Will respawn queued item: {item_text} at {current_time}ms")
            
            # Remove from queue after scheduling for respawn
            self.level_queue.remove(item_text)
            
            # Add to dropped_correct if not already there
            if item_text not in self.dropped_correct:
                self.dropped_correct.append(item_text)
        
        # Then add remaining correct items
        for item_text in remaining_correct:
            if item_text in [e['item_text'] for e in self.spawn_events]:
                continue  # Skip if already in spawn_events from queue
                
            delay = random.randint(400, 1200) if self.spawn_events else 0
            current_time += delay
            
            self.spawn_events.append({
                'time': current_time,
                'item_text': item_text,
                'category': self.target_category
            })
            self.dropped_correct.append(item_text)
            print(f"  - Will spawn remaining correct item: {item_text} at {current_time}ms")
        
        # Add additional random items if needed
        for _ in range(additional_items):
            delay = random.randint(400, 1200)
            current_time += delay
            
            item_text, category = self.get_new_item()
            
            # Make sure we don't spawn a correct item as a wrong item
            while category != self.target_category and item_text in self.correct_items:
                item_text, category = self.get_new_item()
            
            self.spawn_events.append({
                'time': current_time,
                'item_text': item_text,
                'category': category
            })
            print(f"  - Will spawn random item: {item_text} ({category}) at {current_time}ms")
            
        print(f"Total spawn events prepared: {len(self.spawn_events)}")
        
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

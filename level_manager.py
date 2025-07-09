"""Level Manager Module

This module provides the LevelManager class which handles level progression,
item spawning, and level completion logic for the game.
"""

import random
import pygame
from typing import Dict, List, Optional, Set, Tuple, TypedDict

from settings import *


class SpawnEvent(TypedDict):
    """Type definition for spawn events.
    
    Attributes:
        time: The game time when the item should spawn.
        item_text: The text of the item to spawn.
        category: The category of the item.
    """
    time: int
    item_text: str
    category: str

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
        """Initialize a new LevelManager with default values."""
        self.level: int = 1
        self.target_category: Optional[str] = None
        self.correct_items: List[str] = []
        self.dropped_correct: List[str] = []
        self.caught_correct: List[str] = []
        self.level_queue: List[str] = []  # Queue of items to be respawned
        self.available_quantities: Dict[str, List[str]] = {
            key: value[:] for key, value in ALL_QUANTITIES.items()
        }
        
        # Spawn management
        self.spawn_events: List[SpawnEvent] = []
        self.spawn_index: int = 0
        self.item_spawned_count: int = 0
        self.total_items_to_spawn: int = 0
        self.spawn_ready: bool = False
    
    def setup_level(self, level: int) -> None:
        """Set up a new level with the given level number.
        
        Args:
            level: The level number to set up.
            
        Raises:
            KeyError: If the level number is invalid.
        """
        if level not in LEVEL_TARGETS:
            raise ValueError(f"Invalid level number: {level}")
            
        self.level = level
        self.target_category = LEVEL_TARGETS[level]
        self.correct_items = ALL_QUANTITIES[self.target_category][:]
        self.dropped_correct = []
        self.caught_correct = []
        self.level_queue = self.correct_items.copy()  # Initialize level queue with correct items
        
        # Reset spawn state
        self.spawn_events = []
        self.spawn_index = 0
        self.item_spawned_count = 0
        self.total_items_to_spawn = 0
        self.spawn_ready = False
        
        # Reset available quantities
        self.available_quantities = {
            key: value[:] for key, value in ALL_QUANTITIES.items()
        }
        
        print(f"Level {level} setup complete. Target category: {self.target_category}")
        print(f"Correct items: {', '.join(self.correct_items)}")
        print(f"Level queue initialized with {len(self.level_queue)} items")
    
    def get_new_item(self) -> Tuple[str, str]:
        """Get a new item for the current level.
        
        Returns:
            A tuple of (item_text, item_category) where:
            - item_text: The text of the item
            - item_category: The category of the item
            
        Note:
            - Always prioritize spawning remaining correct items
            - 40% chance to spawn wrong items from other levels
            - Ensures wrong items are different from correct ones
        """
        # Always try to spawn remaining correct items first
        remaining_correct = [
            item for item in self.correct_items 
            if item not in self.caught_correct and item not in self.dropped_correct
        ]
        
        if remaining_correct and random.random() > 0.4:  # 60% chance to spawn correct item if available
            item_text = random.choice(remaining_correct)
            return item_text, self.target_category
            
        # 40% chance to spawn wrong item from other levels
        # Get all possible wrong items from other levels
        wrong_items = []
        for category, items in ALL_QUANTITIES.items():
            if category != self.target_category:  # Only from other levels
                for item in items:
                    # Only include items that aren't correct items in current level
                    if item not in self.correct_items:
                        wrong_items.append((item, category))
        
        if wrong_items:
            return random.choice(wrong_items)
            
        # Fallback: if no wrong items found, return a correct one
        if remaining_correct:
            return random.choice(remaining_correct), self.target_category
            
        # Last resort: return any item
        category = random.choice(list(ALL_QUANTITIES.keys()))
        return random.choice(ALL_QUANTITIES[category]), category
    
    def prepare_spawn_events(self, min_items: int = 3, max_items: int = 6) -> None:
        """Prepare the spawn events for the current level.
        
        Args:
            min_items: Minimum number of items to spawn.
            max_items: Maximum number of items to spawn.
            
        Note:
            - Ensures all correct items are spawned before completing the level
            - Randomly spawns wrong items from other levels
            - Sets up spawn times with random delays between items
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

"""Core data models for the game editor."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Game:
    """Represents a game in the system."""
    id: int
    name: str
    description: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the game to a dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Game':
        """Create a Game instance from a dictionary."""
        return cls(
            id=data['id'],
            name=data['name'],
            description=data.get('description', ''),
            created_at=datetime.fromisoformat(data['created_at']),
            updated_at=datetime.fromisoformat(data['updated_at'])
        )


@dataclass
class Level:
    """Represents a game level."""
    id: int
    game_id: int
    level_number: int
    level_name: str
    level_description: str = ""
    wrong_answer_percentage: int = 20
    item_speed: float = 2.0
    max_items_on_screen: int = 5
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the level to a dictionary."""
        return {
            'id': self.id,
            'game_id': self.game_id,
            'level_number': self.level_number,
            'level_name': self.level_name,
            'level_description': self.level_description,
            'wrong_answer_percentage': self.wrong_answer_percentage,
            'item_speed': self.item_speed,
            'max_items_on_screen': self.max_items_on_screen,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Level':
        """Create a Level instance from a dictionary."""
        return cls(
            id=data['id'],
            game_id=data['game_id'],
            level_number=data['level_number'],
            level_name=data['level_name'],
            level_description=data.get('level_description', ''),
            wrong_answer_percentage=data.get('wrong_answer_percentage', 20),
            item_speed=float(data.get('item_speed', 2.0)),
            max_items_on_screen=int(data.get('max_items_on_screen', 5)),
            created_at=datetime.fromisoformat(data['created_at']),
            updated_at=datetime.fromisoformat(data['updated_at'])
        )


@dataclass
class Expression:
    """Represents a game expression (question/answer)."""
    id: int
    level_id: int
    expression: str
    is_correct: bool
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the expression to a dictionary."""
        return {
            'id': self.id,
            'level_id': self.level_id,
            'expression': self.expression,
            'is_correct': self.is_correct,
            'created_at': self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Expression':
        """Create an Expression instance from a dictionary."""
        return cls(
            id=data['id'],
            level_id=data['level_id'],
            expression=data['expression'],
            is_correct=bool(data['is_correct']),
            created_at=datetime.fromisoformat(data['created_at'])
        )


@dataclass
class GameSettings:
    """Represents game settings."""
    game_id: int
    settings: Dict[str, str] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a setting value by key."""
        return self.settings.get(key, default)
    
    def set(self, key: str, value: str) -> None:
        """Set a setting value."""
        self.settings[key] = value
        self.updated_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the settings to a dictionary."""
        return {
            'game_id': self.game_id,
            'settings': self.settings,
            'updated_at': self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GameSettings':
        """Create a GameSettings instance from a dictionary."""
        return cls(
            game_id=data['game_id'],
            settings=dict(data.get('settings', {})),
            updated_at=datetime.fromisoformat(data['updated_at'])
        )


@dataclass
class Sprite:
    """Represents a sprite sheet file."""
    id: int
    game_id: int
    name: str
    path: str
    created_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Sprite':
        return cls(
            id=data['id'],
            game_id=data['game_id'],
            name=data['name'],
            path=data['path'],
            created_at=datetime.fromisoformat(data['created_at'])
        )


@dataclass
class SpriteDefinition:
    """Represents a single sprite's coordinates within a sprite sheet, linked to an expression."""
    id: int
    sprite_id: int
    expression_id: int
    x: int
    y: int
    width: int
    height: int
    created_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SpriteDefinition':
        return cls(
            id=data['id'],
            sprite_id=data['sprite_id'],
            expression_id=data['expression_id'],
            x=data['x'],
            y=data['y'],
            width=data['width'],
            height=data['height'],
            created_at=datetime.fromisoformat(data['created_at'])
        )


@dataclass
class Screen:
    """Represents a designed screen (e.g., opening) stored as JSON in DB.

    The JSON payload contains layout and widget definitions. This model mirrors the
    `screens` table structure for editor operations.
    """
    id: int
    game_id: int
    name: str
    type: str
    data_json: str
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Screen':
        """Create a Screen instance from a dictionary."""
        return cls(
            id=data['id'],
            game_id=data['game_id'],
            name=data['name'],
            type=data['type'],
            data_json=data['data_json'],
            created_at=datetime.fromisoformat(data.get('created_at')) if data.get('created_at') else datetime.now(),
            updated_at=datetime.fromisoformat(data.get('updated_at')) if data.get('updated_at') else datetime.now()
        )
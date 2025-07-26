"""Donetick models."""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
  
)


_LOGGER = logging.getLogger(__name__)

@dataclass
class DonetickAssignee:
    """Donetick assignee model."""
    user_id: int

@dataclass
class DonetickTask:
    """Donetick task model."""
    id: int
    name: str
    next_due_date: Optional[datetime]
    status: int
    priority: int
    labels: Optional[str]
    is_active: bool
    frequency_type: str
    frequency: int
    frequency_metadata: str
    
    @classmethod
    def from_json(cls, data: dict) -> "DonetickTask":
        """Create a DonetickTask from JSON data."""
        return cls(
            id=data["id"],
            name=data["name"],
            next_due_date=datetime.fromisoformat(data["nextDueDate"].replace('Z', '+00:00')) if data.get("nextDueDate") else None,
            status=data["status"],
            priority=data["priority"],
            labels=data["labels"],
            is_active=data["isActive"],
            frequency_type=data["frequencyType"],
            frequency=data["frequency"],
            frequency_metadata=data["frequencyMetadata"]
        )
    
    @classmethod
    def from_json_list(cls, data: List[dict]) -> List["DonetickTask"]:
        """Create a list of DonetickTasks from JSON data."""
        return [cls.from_json(task) for task in data]

@dataclass
class DonetickThing:
    """Donetick thing model."""
    id: int
    name: str
    state: str

    @classmethod
    def from_json(cls, data: dict) -> "DonetickThing":
        """Create a DonetickThing from JSON data."""
        return cls(
            id=data["id"],
            name=data["name"],
            state=data["state"],
        )

    @classmethod
    def from_json_list(cls, data: List[dict]) -> List["DonetickThing"]:
        """Create a list of DonetickThings from JSON data."""
        return [cls.from_json(thing) for thing in data]
    

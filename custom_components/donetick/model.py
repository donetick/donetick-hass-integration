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
class DonetickMember:
    """Donetick circle member model."""
    id: int
    user_id: int
    circle_id: int
    role: str
    is_active: bool
    username: str
    display_name: str
    image: Optional[str] = None
    points: int = 0
    points_redeemed: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    @classmethod
    def from_json(cls, data: dict) -> "DonetickMember":
        """Create a DonetickMember from JSON data."""
        return cls(
            id=data["id"],
            user_id=data["userId"],
            circle_id=data["circleId"],
            role=data["role"],
            is_active=data["isActive"],
            username=data["username"],
            display_name=data["displayName"],
            image=data.get("image"),
            points=data.get("points", 0),
            points_redeemed=data.get("pointsRedeemed", 0),
            created_at=data.get("createdAt"),
            updated_at=data.get("updatedAt")
        )
    
    @classmethod
    def from_json_list(cls, data: List[dict]) -> List["DonetickMember"]:
        """Create a list of DonetickMembers from JSON data."""
        return [cls.from_json(member) for member in data]

@dataclass
class DonetickAssignee:
    """Donetick assignee model."""
    user_id: int

@dataclass
class DonetickLabel:
    """Donetick label model."""
    id: Optional[int]
    name: str
    color: Optional[str] = None

    @classmethod
    def from_json(cls, data: dict) -> "DonetickLabel":
        return cls(
            id=data.get("id"),
            name=data.get("name", ""),
            color=data.get("color"),
        )


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
    assigned_to: Optional[int] = None
    description: Optional[str] = None
    labels_v2: Optional[List[DonetickLabel]] = None
    label_names: Optional[List[str]] = None
    label_names_normalized: Optional[List[str]] = None
    
    @classmethod
    def from_json(cls, data: dict) -> "DonetickTask":
        """Create a DonetickTask from JSON data."""
        # Handle assignedTo field - could be in different formats
        assigned_to = None
        if data.get("assignedTo"):
            if isinstance(data["assignedTo"], int):
                assigned_to = data["assignedTo"]
        labels_v2: Optional[List[DonetickLabel]] = None
        label_names: List[str] = []
        if isinstance(data.get("labelsV2"), list):
            labels_v2 = [DonetickLabel.from_json(label) for label in data["labelsV2"]]
            label_names = [label.name for label in labels_v2 if label.name]
        elif data.get("labels"):
            label_names = [label.strip() for label in data["labels"].split(",") if label.strip()]
        label_names_normalized = [name.lower() for name in label_names]
          
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
            frequency_metadata=data["frequencyMetadata"],
            assigned_to=assigned_to,
            description=data.get("description"),
            labels_v2=labels_v2,
            label_names=label_names or None,
            label_names_normalized=label_names_normalized or None,
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
    type: str  # text, number, boolean, action
    state: str
    user_id: int
    circle_id: int
    updated_at: Optional[str] = None
    created_at: Optional[str] = None
    thing_chores: Optional[List] = None
    
    @classmethod
    def from_json(cls, data: dict) -> "DonetickThing":
        """Create a DonetickThing from JSON data."""
        return cls(
            id=data["id"],
            name=data["name"],
            type=data["type"],
            state=str(data["state"]),
            user_id=data["userID"],
            circle_id=data["circleId"],
            updated_at=data.get("updatedAt"),
            created_at=data.get("createdAt"),
            thing_chores=data.get("thingChores")
        )
    
    @classmethod
    def from_json_list(cls, data: List[dict]) -> List["DonetickThing"]:
        """Create a list of DonetickThings from JSON data."""
        return [cls.from_json(thing) for thing in data]
    

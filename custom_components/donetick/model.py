"""Donetick models."""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, List
from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
  
)


_LOGGER = logging.getLogger(__name__)


def _parse_datetime(value: Any) -> Optional[datetime]:
    """Parse a Donetick timestamp, returning None for empty or invalid values."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _LOGGER.debug("Unable to parse Donetick datetime: %s", value)
        return None

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
class DonetickTask:
    """Donetick task model."""
    id: int
    name: str
    next_due_date: Optional[datetime]
    status: int
    priority: int
    labels: Optional[Any]
    is_active: bool
    is_rolling: bool
    frequency_type: str
    frequency: int
    frequency_metadata: Optional[Any]
    assigned_to: Optional[int] = None
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_completed_date: Optional[datetime] = None
    last_completed_by: Optional[int] = None
    duration: Optional[int] = None
    start_time: Optional[datetime] = None
    timer_updated_at: Optional[datetime] = None
    
    @classmethod
    def from_json(cls, data: dict) -> "DonetickTask":
        """Create a DonetickTask from JSON data."""
        # Handle assignedTo field - could be in different formats
        assigned_to = None
        if data.get("assignedTo"):
            if isinstance(data["assignedTo"], int):
                assigned_to = data["assignedTo"]
          
        return cls(
            id=data["id"],
            name=data["name"],
            next_due_date=_parse_datetime(data.get("nextDueDate")),
            status=data.get("status", 0),
            priority=data.get("priority", 0),
            labels=data.get("labels") or data.get("labelsV2"),
            is_active=data.get("isActive", True),
            is_rolling=data.get("isRolling", False),
            frequency_type=data.get("frequencyType", "once"),
            frequency=data.get("frequency") or 1,
            frequency_metadata=data.get("frequencyMetadata"),
            assigned_to=assigned_to,
            description=data.get("description"),
            created_at=_parse_datetime(data.get("createdAt")),
            updated_at=_parse_datetime(data.get("updatedAt")),
            last_completed_date=_parse_datetime(data.get("lastCompletedDate")),
            last_completed_by=data.get("lastCompletedBy"),
            duration=data.get("duration"),
            start_time=_parse_datetime(data.get("startTime")),
            timer_updated_at=_parse_datetime(data.get("timerUpdatedAt")),
        )
    
    @classmethod
    def from_json_list(cls, data: List[dict]) -> List["DonetickTask"]:
        """Create a list of DonetickTasks from JSON data."""
        return [cls.from_json(task) for task in data]


@dataclass
class DonetickChoreHistory:
    """Donetick chore history model."""
    id: int
    chore_id: int
    performed_at: Optional[datetime]
    completed_by: Optional[int]
    assigned_to: Optional[int]
    due_date: Optional[datetime]
    status: int
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    duration: Optional[int] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    timer_updated_at: Optional[datetime] = None

    @classmethod
    def from_json(cls, data: dict) -> "DonetickChoreHistory":
        """Create a DonetickChoreHistory from JSON data."""
        return cls(
            id=data["id"],
            chore_id=data["choreId"],
            performed_at=_parse_datetime(data.get("performedAt")),
            completed_by=data.get("completedBy"),
            assigned_to=data.get("assignedTo"),
            due_date=_parse_datetime(data.get("dueDate")),
            status=data.get("status", 0),
            notes=data.get("notes"),
            created_at=_parse_datetime(data.get("createdAt")),
            updated_at=_parse_datetime(data.get("updatedAt")),
            duration=data.get("duration"),
            start_time=_parse_datetime(data.get("startTime")),
            end_time=_parse_datetime(data.get("endTime")),
            timer_updated_at=_parse_datetime(data.get("timerUpdatedAt")),
        )

    @classmethod
    def from_json_list(cls, data: List[dict]) -> List["DonetickChoreHistory"]:
        """Create a list of DonetickChoreHistory objects from JSON data."""
        return [cls.from_json(history) for history in data]

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
    

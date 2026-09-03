from dataclasses import dataclass, field
from typing import List, Set


@dataclass
class LaunchContext:
    """Represents the customer's current launch context."""

    release: str
    market: str
    available_modules: Set[str] = field(default_factory=set)


@dataclass
class Activity:
    """A parsed, validated activity from the activity library."""

    id: str
    release: str
    markets: List[str]
    required_modules: List[str]

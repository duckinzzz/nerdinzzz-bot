"""Base Tool dataclass — the single interface every tool must implement."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Tool:
    """A tool that the LLM can call.

    Attributes:
        name: Unique tool identifier (e.g. "get_weather").
        description: What the tool does — shown to the LLM.
        parameters: JSON Schema for the tool's arguments.
        execute: Async callable that receives keyword arguments and returns a string.
    """

    name: str
    description: str
    parameters: dict[str, Any]
    execute: Callable[..., Awaitable[str]]

    # Internal bookkeeping — not part of the public API
    _registered: bool = field(default=False, repr=False)

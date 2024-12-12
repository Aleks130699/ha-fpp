"""PyArr constants."""

from __future__ import annotations

from enum import Enum
from logging import Logger, getLogger
from typing import Final

LOGGER: Final[Logger] = getLogger(__package__)


class HTTPMethod(Enum):
    """HTTPMethod Enum."""

    DELETE = "DELETE"
    GET = "GET"
    POST = "POST"
    PUT = "PUT"


REQUEST_TIMEOUT: Final = 10
DEFAULT_VERIFY_SSL: Final = True

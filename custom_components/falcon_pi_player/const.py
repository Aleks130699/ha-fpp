"""Constants for the Falcon Pi Player integration."""

from __future__ import annotations

from logging import Logger, getLogger
from typing import Final

DOMAIN: Final[str] = "falcon_pi_player"
DEFAULT_NAME: Final[str] = "FPP"
DEFAULT_URL: Final[str] = "http://fpp.local"
DEFAULT_VERIFY_SSL: Final[bool] = False
DEFAULT_USERNAME: Final[str] = "admin"
DEFAULT_PASSWORD: Final[str] = "falcon"
UPDATE_INTERVAL_SECONDS: Final[int] = 5

LOGGER: Final[Logger] = getLogger(__package__)

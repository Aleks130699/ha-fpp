"""Data update coordinator for the FPP integration."""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Any
from datetime import timedelta
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, UPDATE_INTERVAL_SECONDS
from .fpp_client.fpp_client import FPPClient,
from .fpp_client.exceptions import FPPConnectionException, FPPAuthenticationException

if TYPE_CHECKING:
    from . import FPPConfigEntry


class FPPDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Data update coordinator for the FPP integration."""

    config_entry: FPPConfigEntry
    _update_interval = timedelta(seconds=UPDATE_INTERVAL_SECONDS)

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: FPPClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=self._update_interval,
        )
        self.api_client = api_client

    async def _async_update_data(self) -> T:
        """Get the latest data from FPP."""
        try:
            return await self._fetch_data()

        except FPPConnectionException as ex:
            raise UpdateFailed(ex) from ex
        except FPPAuthenticationException as ex:
            raise ConfigEntryAuthFailed(
                "Username and Password not correct. Please reauthenticate"
            ) from ex

    @abstractmethod
    async def _fetch_data(self) -> dict[str, Any]:
        """Fetch the actual data."""
        raise NotImplementedError


class SystemStatusUpdateCoordinator(FPPDataUpdateCoordinator[dict[str, Any]]):
    """Status update coordinator for FPP."""

    async def _fetch_data(self) -> dict[str, Any]:
        """Fetch the data."""
        return await self.api_client.async_get_system_status()

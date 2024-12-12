"""The Falcon Pi Player integration."""

from __future__ import annotations

from dataclasses import dataclass, fields

from aiohttp import BasicAuth

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import FPPDataUpdateCoordinator, SystemStatusUpdateCoordinator
from .fpp_client.fpp_client import FPPClient

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]


@dataclass(kw_only=True, slots=True)
class FPPData:
    """Data for FPP integration."""

    system_status: SystemStatusUpdateCoordinator


type FPPConfigEntry = ConfigEntry[FPPData]


async def async_setup_entry(hass: HomeAssistant, entry: FPPConfigEntry) -> bool:
    """Set up Falcon Pi Player from a config entry."""

    # Build Client Params
    auth: BasicAuth | None = None
    if entry.data[CONF_USERNAME] and entry.data[CONF_PASSWORD]:
        auth = BasicAuth(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    session = async_get_clientsession(hass, entry.data[CONF_VERIFY_SSL])

    # Setup Client
    fpp_client = FPPClient(url=entry.data[CONF_URL], auth=auth, session=session)

    # Setup Coordinators
    data = FPPData(
        system_status=SystemStatusUpdateCoordinator(hass, fpp_client),
    )

    # Load data for each coordinator
    for field in fields(data):
        coordinator: FPPDataUpdateCoordinator = getattr(data, field.name)
        await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: FPPConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

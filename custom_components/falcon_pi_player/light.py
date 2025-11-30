from __future__ import annotations

import asyncio
import logging

import aiohttp
import voluptuous as vol

from homeassistant.components.light import (
    PLATFORM_SCHEMA as LIGHT_PLATFORM_SCHEMA,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "FPP Brightness"

PLATFORM_SCHEMA = LIGHT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=80): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_USERNAME, default="admin"): cv.string,
        vol.Optional(CONF_PASSWORD, default="falcon"): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the FPP Brightness light from YAML (async)."""
    host = config[CONF_HOST]
    port = config[CONF_PORT]
    name = config.get(CONF_NAME, DEFAULT_NAME)
    username = config.get(CONF_USERNAME, "admin")
    password = config.get(CONF_PASSWORD, "falcon")

    light = FPPBrightnessLight(
        host=host, port=port, name=name, username=username, password=password
    )
    async_add_entities([light], True)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up FPP Brightness light from ConfigEntry (async)."""
    host = entry.data.get(CONF_HOST)
    port = entry.data.get(CONF_PORT)
    name = entry.data.get(CONF_NAME, DEFAULT_NAME)
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)

    light = FPPBrightnessLight(
        host=host, port=port, name=name, username=username, password=password
    )
    async_add_entities([light], True)


class FPPBrightnessLight(LightEntity):
    """Representation of FPP brightness as a Light entity (fully async)."""

    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS

    def __init__(
        self,
        host: str,
        port: str,
        name: str,
        username: str | None,
        password: str | None,
    ) -> None:
        self._host = host
        self._port = port
        self._name = name or DEFAULT_NAME
        self._username = username
        self._pass = password
        self._base_url = (
            f"http://{self._username}:{self._pass}@{self._host}:{self._port}"
        )
        self._attr_is_on = False
        self._attr_brightness = 255
        self._available = False
        self._fade_task = None
        self._session: aiohttp.ClientSession | None = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def unique_id(self) -> str:
        return f"light_fpp_brightness_{self._host}"

    @property
    def device_info(self):
        return {
            "identifiers": {("fpp", self._host)},
            "name": f"{self._name}",
            "manufacturer": "Falcon Player",
            "model": f"FPP [{self._host}]",
            "configuration_url": f"http://{self._host}:{self._port}",
        }

    @property
    def available(self) -> bool:
        return self._available

    async def async_update(self) -> None:
        """Fetch brightness from FPP asynchronously."""
        if self._session is None:
            self._session = aiohttp.ClientSession()

        try:
            url = f"{self._base_url}/api/plugin-apis/Brightness"
            async with self._session.get(url, timeout=10) as resp:
                resp.raise_for_status()
                text = await resp.text()
                value = int(text.strip())
                value = max(0, min(100, value))
                ha_brightness = round(value * 255 / 100)
                self._attr_brightness = ha_brightness
                self._attr_is_on = value > 0
                self._available = True
        except Exception as err:
            _LOGGER.debug(
                "Failed to update FPP brightness from %s: %s", self._host, err
            )
            self._available = False

    async def _async_send_command(self, payload: dict) -> None:
        """Send brightness command to FPP asynchronously."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
        try:
            url = f"{self._base_url}/api/command"
            async with self._session.post(url, json=payload, timeout=10) as resp:
                resp.raise_for_status()
            self._available = True
        except Exception as err:
            _LOGGER.error("Failed to send command to %s: %s", self._host, err)
            self._available = False

    async def _fade_monitor(self):
        """Task to update brightness during fade every 1 second."""
        try:
            while True:
                await self.async_update()
                self.async_write_ha_state()
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            pass

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the light on, optionally setting brightness."""
        brightness_ha = kwargs.get("brightness")
        fade_duration = kwargs.get("transition", 2)
        if brightness_ha is None:
            target_percent = 100
            self._attr_brightness = 255
        else:
            brightness_ha = max(0, min(255, int(brightness_ha)))
            target_percent = round(brightness_ha * 100 / 255)
            self._attr_brightness = brightness_ha

        self._attr_is_on = target_percent > 0
        self.async_write_ha_state()

        await self._async_send_command(
            {
                "command": "Brightness Fade",
                "args": [str(target_percent), str(fade_duration)],
            }
        )

        if self._fade_task:
            self._fade_task.cancel()
        self._fade_task = asyncio.create_task(self._fade_monitor())
        asyncio.create_task(self._stop_fade_monitor_after(fade_duration))

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off (set brightness 0)."""
        fade_duration = kwargs.get("transition", 2)
        self._attr_brightness = 0
        self._attr_is_on = False
        self.async_write_ha_state()

        await self._async_send_command(
            {"command": "Brightness Fade", "args": ["0", str(fade_duration)]}
        )

        if self._fade_task:
            self._fade_task.cancel()
        self._fade_task = asyncio.create_task(self._fade_monitor())
        asyncio.create_task(self._stop_fade_monitor_after(fade_duration))

    async def _stop_fade_monitor_after(self, seconds: int):
        await asyncio.sleep(seconds)
        if self._fade_task:
            self._fade_task.cancel()
            self._fade_task = None
            await self.async_update()
            self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Close aiohttp session when entity is removed."""
        if self._session is not None:
            await self._session.close()
            self._session = None

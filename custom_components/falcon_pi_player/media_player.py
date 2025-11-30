"""Media player platform for Falcon Pi Player."""

from __future__ import annotations

import logging
import urllib.parse

import aiohttp
import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA as MEDIA_PLAYER_PLATFORM_SCHEMA,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    STATE_IDLE,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "FPP"

PLATFORM_SCHEMA = MEDIA_PLAYER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=80): cv.string,
        vol.Required(CONF_NAME, default=DEFAULT_NAME): cv.string,
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
    """Set up the FPP platform from YAML asynchronously."""
    host = config[CONF_HOST]
    port = config[CONF_PORT]
    name = config.get(CONF_NAME, DEFAULT_NAME)
    username = config.get(CONF_USERNAME, "admin")
    password = config.get(CONF_PASSWORD, "falcon")

    fpp = FPP(
        hass=hass, host=host, port=port, name=name, username=username, password=password
    )

    async_add_entities([fpp], True)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up FPP via ConfigEntry asynchronously."""
    host: str = entry.data[CONF_HOST]
    port: str = entry.data[CONF_PORT]
    name: str = entry.data.get(CONF_NAME, DEFAULT_NAME)
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)

    fpp = FPP(
        hass=hass, host=host, port=port, name=name, username=username, password=password
    )
    async_add_entities([fpp], True)


class FPP(MediaPlayerEntity):
    """Async FPP Player."""

    _attr_supported_features = (
        MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
    )

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: str,
        name: str,
        username: str | None,
        password: str | None,
    ) -> None:
        """Initialize the FPP media player."""
        self._hass = hass
        self._host = host
        self._port = port
        self._name = name or DEFAULT_NAME
        self._attr_name = name
        self._username = username
        self._pass = password
        if username and password:
            self._base_url = (
                f"http://{self._username}:{self._pass}@{self._host}:{self._port}"
            )
        else:
            self._base_url = f"http://{self._host}:{self._port}"
        self._state = STATE_IDLE
        self._attr_media_content_type = MediaType.MUSIC
        self._attr_unique_id = f"media_player_{name}"
        self._available = False

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information for the FPP."""
        return {
            "identifiers": {("fpp", self._host)},
            "name": f"{self._name}",
            "manufacturer": "Falcon Player",
            "model": f"FPP [{self._host}]",
            "configuration_url": f"http://{self._host}:{self._port}",
        }

    async def async_update(self) -> None:
        """Async update FPP state."""
        session = async_get_clientsession(self._hass)

        try:
            status_url = f"{self._base_url}/api/system/status"
            async with session.get(
                status_url, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                status = await resp.json()

            if status.get("fppd") != "running":
                self._state = STATE_OFF
                self._available = False
                return

            self._state = status.get("status_name")
            self._attr_volume_level = status.get("volume", 0) / 100

            if self._state == STATE_PLAYING:
                self._attr_media_title = (
                    status.get("current_sequence", "").replace(".fseq", "")
                    if status.get("current_sequence")
                    else status.get("current_song", "")
                    .replace(".mp3", "")
                    .replace(".mp4", "")
                )
                self._attr_media_playlist = status.get("current_playlist", {}).get(
                    "playlist"
                )
                self._attr_source = self._attr_media_playlist
                self._attr_media_duration = int(status.get("seconds_played", 0)) + int(
                    status.get("seconds_remaining", 0)
                )
                self._attr_media_position = int(status.get("seconds_played", 0))
                self._attr_media_position_updated_at = dt_util.utcnow()
                image_url = (
                    f"{self._base_url}/api/file/Images/{self._attr_media_title}.jpg"
                )
                try:
                    async with session.head(
                        image_url, timeout=aiohttp.ClientTimeout(total=5)
                    ) as img_resp:
                        if img_resp.status == 200:
                            self._attr_media_image_url = image_url
                        else:
                            self._attr_media_image_url = None
                except aiohttp.ClientError:
                    self._attr_media_image_url = None
            else:
                self._attr_media_title = None
                self._attr_media_playlist = None
                self._attr_media_duration = None
                self._attr_media_position = None
                self._attr_media_position_updated_at = None
                self._attr_media_image_url = None

            playlists_url = f"{self._base_url}/api/playlists/playable"
            async with session.get(
                playlists_url, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                self._attr_source_list = await resp.json()

            self._available = True
        except aiohttp.ClientError as e:
            _LOGGER.error("Error updating FPP: %s", e)
            self._state = STATE_OFF
            self._available = False

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the player."""
        if self._state in [None, STATE_OFF, "stopped"]:
            return MediaPlayerState.OFF
        if self._state == STATE_IDLE:
            return MediaPlayerState.IDLE
        if self._state == STATE_PLAYING:
            return MediaPlayerState.PLAYING
        if self._state == STATE_PAUSED:
            return MediaPlayerState.PAUSED
        return MediaPlayerState.IDLE

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    async def _async_send_command(
        self, url: str, method: str = "get", json_data: dict | None = None
    ) -> None:
        """Send a command to the FPP device."""
        session = async_get_clientsession(self._hass)
        try:
            if method == "get":
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)):
                    pass
            else:
                async with session.post(
                    url, json=json_data, timeout=aiohttp.ClientTimeout(total=10)
                ):
                    pass
        except aiohttp.ClientError as e:
            _LOGGER.error("Error sending command to FPP: %s", e)

    async def async_turn_off(self) -> None:
        """Turn off the media player."""
        await self._async_send_command(f"{self._base_url}/api/system/fppd/stop")

    async def async_turn_on(self) -> None:
        """Turn on the media player."""
        await self._async_send_command(f"{self._base_url}/api/system/fppd/start")

    async def async_select_source(self, source: str) -> None:
        """Select a source (playlist)."""
        playlist_url = urllib.parse.quote_plus(source)
        await self._async_send_command(
            f"{self._base_url}/api/playlist/{playlist_url}/start"
        )

    async def async_set_volume_level(self, volume: float) -> None:
        """Set the volume level."""
        volume_int = int(volume * 100)
        await self._async_send_command(
            f"{self._base_url}/api/command",
            method="post",
            json_data={"command": "Volume Set", "args": [volume_int]},
        )

    async def async_volume_up(self) -> None:
        """Increase volume by one step."""
        await self._async_send_command(
            f"{self._base_url}/api/command",
            method="post",
            json_data={"command": "Volume Increase", "args": ["1"]},
        )

    async def async_volume_down(self) -> None:
        """Decrease volume by one step."""
        await self._async_send_command(
            f"{self._base_url}/api/command",
            method="post",
            json_data={"command": "Volume Decrease", "args": ["1"]},
        )

    async def async_media_stop(self) -> None:
        """Stop the media player."""
        await self._async_send_command(f"{self._base_url}/api/playlists/stop")

    async def async_media_play(self) -> None:
        """Play the media player."""
        await self._async_send_command(f"{self._base_url}/api/playlists/resume")

    async def async_media_pause(self) -> None:
        """Pause the media player."""
        await self._async_send_command(f"{self._base_url}/api/playlists/pause")

    async def async_media_next_track(self) -> None:
        """Skip to the next track."""
        await self._async_send_command(
            f"{self._base_url}/api/command/Next Playlist Item"
        )

    async def async_media_previous_track(self) -> None:
        """Skip to the previous track."""
        await self._async_send_command(
            f"{self._base_url}/api/command/Prev Playlist Item"
        )

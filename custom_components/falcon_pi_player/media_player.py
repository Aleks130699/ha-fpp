from __future__ import annotations

import logging
import urllib.parse
import aiohttp
import asyncio

import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA as MEDIA_PLAYER_PLATFORM_SCHEMA,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
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
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
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

    fpp = FPP(host=host, port=port, name=name, username=username, password=password)

    async_add_entities([fpp], True)

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
    ) -> None:
    """Set up FPP via ConfigEntry asynchronously."""
    host = entry.data.get(CONF_HOST)
    port = entry.data.get(CONF_PORT)
    name = entry.data.get(CONF_NAME, DEFAULT_NAME)
    username = entry.data.get(CONF_USERNAME, "admin")
    password = entry.data.get(CONF_PASSWORD, "falcon")

    fpp = FPP(host=host, port=port, name=name, username=username, password=password)
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

    def __init__(self, host: str, port: str, name: str, username: str | None, password: str | None) -> None:
        self._host = host
        self._port = port
        self._name = name or DEFAULT_NAME
        self._attr_name = name
        self._username = username
        self._pass = password
        self._base_url = f"http://{self._username}:{self._pass}@{self._host}:{self._port}"
        self._state = STATE_IDLE
        self._attr_media_content_type = MediaType.MUSIC
        self._attr_unique_id = f"media_player_{name}"
        self._available = False
        self._session: aiohttp.ClientSession | None = None

    @property
    def device_info(self):
        return {
            "identifiers": {("fpp", self._host)},
            "name": f"{self._name}",
            "manufacturer": "Falcon Player",
            "model": f"FPP [{self._host}]",
            "configuration_url": f"http://{self._host}:{self._port}",
        }

    async def async_update(self) -> None:
        """Async update FPP state."""
        if self._session is None:
            self._session = aiohttp.ClientSession()

        try:
            status_url = f"{self._base_url}/api/system/status"
            async with self._session.get(status_url, timeout=10) as resp:
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
                    if status.get("current_sequence") else status.get("current_song", "").replace(".mp3", "").replace(".mp4", "")
                )
                self._attr_media_playlist = status.get("current_playlist", {}).get("playlist")
                self._attr_source = self._attr_media_playlist
                self._attr_media_duration = int(status.get("seconds_played", 0)) + int(status.get("seconds_remaining", 0))
                self._attr_media_position = int(status.get("seconds_played", 0))
                self._attr_media_position_updated_at = dt_util.utcnow()
                image_url = f"{self._base_url}/api/file/Images/{self._attr_media_title}.jpg"
                async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(self._username, self._pass)) as session:
                    try:
                        async with session.head(image_url, timeout=5) as img_resp:
                            if img_resp.status == 200:
                                self._attr_media_image_url = image_url
                            else:
                                self._attr_media_image_url = None
                    except Exception:
                        self._attr_media_image_url = None
            else:
                self._attr_media_title = None
                self._attr_media_playlist = None
                self._attr_media_duration = None
                self._attr_media_position = None
                self._attr_media_position_updated_at = None
                self._attr_media_image_url = None

            playlists_url = f"{self._base_url}/api/playlists/playable"
            async with self._session.get(playlists_url, timeout=10) as resp:
                self._attr_source_list = await resp.json()

            self._available = True
        except Exception as e:
            _LOGGER.error("Error updating FPP: %s", e)
            self._state = STATE_OFF
            self._available = False

    @property
    def state(self) -> MediaPlayerState | None:
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
        return self._available

    async def _async_send_command(self, url: str, method: str = "get", json_data: dict | None = None) -> None:
        if self._session is None:
            self._session = aiohttp.ClientSession()
        try:
            if method == "get":
                async with self._session.get(url, timeout=10):
                    pass
            else:
                async with self._session.post(url, json=json_data, timeout=10):
                    pass
        except Exception as e:
            _LOGGER.error("Error sending command to FPP: %s", e)

    async def async_turn_off(self) -> None:
        await self._async_send_command(f"{self._base_url}/api/system/fppd/stop")

    async def async_turn_on(self) -> None:
        await self._async_send_command(f"{self._base_url}/api/system/fppd/start")

    async def async_select_source(self, source: str) -> None:
        playlist_url = urllib.parse.quote_plus(source)
        await self._async_send_command(f"{self._base_url}/api/playlist/{playlist_url}/start")

    async def async_set_volume_level(self, volume: float) -> None:
        volume_int = int(volume * 100)
        await self._async_send_command(
            f"{self._base_url}/api/command", method="post", json_data={"command": "Volume Set", "args": [volume_int]}
        )

    async def async_volume_up(self) -> None:
        await self._async_send_command(
            f"{self._base_url}/api/command", method="post", json_data={"command": "Volume Increase", "args": ["1"]}
        )

    async def async_volume_down(self) -> None:
        await self._async_send_command(
            f"{self._base_url}/api/command", method="post", json_data={"command": "Volume Decrease", "args": ["1"]}
        )

    async def async_media_stop(self) -> None:
        await self._async_send_command(f"{self._base_url}/api/playlists/stop")

    async def async_media_play(self) -> None:
        await self._async_send_command(f"{self._base_url}/api/playlists/resume")

    async def async_media_pause(self) -> None:
        await self._async_send_command(f"{self._base_url}/api/playlists/pause")

    async def async_media_next_track(self) -> None:
        await self._async_send_command(f"{self._base_url}/api/command/Next Playlist Item")

    async def async_media_previous_track(self) -> None:
        await self._async_send_command(f"{self._base_url}/api/command/Prev Playlist Item")

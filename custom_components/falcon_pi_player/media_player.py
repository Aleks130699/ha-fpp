"""Support for the FPP."""

from __future__ import annotations

import logging
import socket
import urllib.parse

import aiohttp
import requests
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
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import FPPConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: FPPConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Setup the FPP Media Player."""

    host = entry.data.get(CONF_HOST)
    port = entry.data.get(CONF_PORT)
    name = entry.data.get(CONF_NAME)
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)
    base_url: str = f"http://{username}:{password}@{host}:{port}"
    url = f"{base_url}/api/system/status"
    async with aiohttp.ClientSession() as session:
        response = await session.get(url)
        content = await response.json()

    fpp = FPP(host=host, port=port, name=name, username=username, password=password)

    async_add_entities([fpp], True)


class FPP(MediaPlayerEntity):
    """Representation of a FPP Media Player."""

    _attr_supported_features = (
        MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.STOP
        # | MediaPlayerEntityFeature.TURN_OFF
        # | MediaPlayerEntityFeature.TURN_ON
        # | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
    )

    def __init__(
        self,
        host: str,
        port: str,
        name: str,
        username: str | None,
        password: str | None,
    ) -> None:
        """Initialize the Player."""
        self._host: str = host
        self._port: str = port
        self._attr_name: str = name
        self._username: str | None = username
        self._pass: str | None = password
        self._base_url: str = (
            f"http://{self._username}:{self._pass}@{self._host}:{self._port}"
        )
        self._state = STATE_IDLE
        self._attr_media_content_type = MediaType.MUSIC
        self._attr_unique_id: str = f"media_player_{name}"
        self._available: bool = False

    def update(self) -> None:
        """Get the latest state from the player."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((self._host, int(self._port)))
        if result != 0:
            self._state = STATE_OFF
            self._available = False
        else:
            # Pulls status even if fppd is not running.
            status_url = f"{self._base_url}/api/system/status"
            status = requests.get(
                url=status_url,
                timeout=10,
            ).json()

            if status.get("fppd") != "running":
                return

            self._state = status.get("status_name")

            self._attr_volume_level = (
                status.get("volume") / 100 if status.get("volume") else 0
            )
            if self._state == STATE_PLAYING:
                self._attr_media_title = (
                    status.get("current_sequence", "").replace(".fseq", "")
                    if status.get("current_sequence", "") != ""
                    else status.get("current_song", "")
                    .replace(".mp3", "")
                    .replace(".mp4", "")
                )
                self._attr_media_playlist = status.get("current_playlist", []).get(
                    "playlist"
                )
                self._attr_source = self._attr_media_playlist
                self._attr_media_duration = int(status.get("seconds_played", 0)) + int(
                    status.get("seconds_remaining", 0)
                )
                self._attr_media_position = int(status.get("seconds_played", 0))
                self._attr_media_position_updated_at = dt_util.utcnow()
                self._attr_media_image_url = (
                    f"{self._base_url}/api/file/Images/{self._attr_media_title}.jpg"
                )

            elif self._state != STATE_PAUSED:
                self._attr_media_title = None
                self._attr_media_playlist = None
                self._attr_media_duration = None
                self._attr_media_position = None
                self._attr_media_position_updated_at = None
                self._attr_media_image_url = None

            playlists_url = f"{self._base_url}/api/playlists/playable"
            playlists = requests.get(
                url=playlists_url,
                timeout=10,
            ).json()
            self._attr_source_list = playlists

            self._available = True

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the device."""
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
        """Media Device is Available."""
        return self._available

    def turn_off(self) -> None:
        """Stop FFP Daemon."""
        url = f"{self._base_url}/api/system/fppd/stop"
        requests.get(
            url=url,
            timeout=10,
        )

    def turn_on(self) -> None:
        """Start FFP Daemon."""
        url = f"{self._base_url}/api/system/fppd/start"
        requests.get(
            url=url,
            timeout=10,
        )

    def select_source(self, source: str) -> None:
        """Choose a playlist to play."""
        playlist_url = urllib.parse.quote_plus(
            source, safe="", encoding=None, errors=None
        )
        url = f"{self._base_url}/api/playlist/{playlist_url}/start"
        requests.get(
            url=url,
            timeout=10,
        )

    def set_volume_level(self, volume: float) -> None:
        """Set volume level."""
        volume = int(volume * 100)
        _LOGGER.debug("fpp volume is %s", volume)
        url = f"{self._base_url}/api/command"
        requests.post(
            url=url,
            json={"command": "Volume Set", "args": [volume]},
            timeout=10,
        )

    def volume_up(self) -> None:
        """Increase volume by 1 step."""
        url = f"{self._base_url}/api/command"
        requests.post(
            url=url,
            json={"command": "Volume Increase", "args": ["1"]},
            timeout=10,
        )

    def volume_down(self) -> None:
        """Decrease volume by 1 step."""
        url = f"{self._base_url}/api/command"
        requests.post(
            url=url,
            json={"command": "Volume Decrease", "args": ["1"]},
            timeout=10,
        )

    def media_stop(self) -> None:
        """Immediately stop all FPP Sequences playing."""
        url = f"{self._base_url}/api/playlists/stop"
        requests.get(
            url=url,
            timeout=10,
        )

    def media_play(self) -> None:
        """Resume FPP Sequences playing."""
        url = f"{self._base_url}/api/playlists/resume"
        requests.get(
            url=url,
            timeout=10,
        )

    def media_pause(self) -> None:
        """Pause FPP Sequences playing."""
        url = f"{self._base_url}/api/playlists/pause"
        requests.get(
            url=url,
            timeout=10,
        )

    def media_next_track(self) -> None:
        """Next FPP Sequences playing."""
        url = f"{self._base_url}/api/command/Next Playlist Item"
        requests.get(
            url=url,
            timeout=10,
        )

    def media_previous_track(self) -> None:
        """Prev FPP Sequences playing."""
        url = f"{self._base_url}/api/command/Prev Playlist Item"
        requests.get(
            url=url,
            timeout=10,
        )

    def media_seek(self, position: float) -> None:
        """Seek FPP Sequences playing."""

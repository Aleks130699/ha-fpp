"""Config flow for the Falcon Pi Player integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.components import onboarding
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

# TODO adjust the data schema to the data that you need
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): str,
        vol.Optional(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): str,
    }
)


class PlaceholderHub:
    """Placeholder class to make tests pass.

    TODO Remove this placeholder class and replace with things from your PyPI package.
    """
    def __init__(self, host: str, port: str, session: aiohttp.ClientSession) -> None:
        """Initialize."""
        self.host = host
        self.port = port
        self.session = session
        self.username: str | None = None
        self.password: str | None = None
        self.base_url: str = f"http://{host}:{port}"

    async def authenticate(self, username: str | None, password: str | None) -> bool:
        """Test if we can authenticate with the host."""
        self.username = username
        self.password = password
        if username and password:
            self.base_url = f"http://{username}:{password}@{self.host}:{self.port}"
        else:
            self.base_url = f"http://{self.host}:{self.port}"
        url = f"{self.base_url}/api/system/status"
        response = await self.session.head(url)
        return response.status == 200


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    # TODO validate the data can be used to set up a connection.

    # If your PyPI package is not built with async, pass your methods
    # to the executor:
    # await hass.async_add_executor_job(
    #     your_validate_func, data[CONF_USERNAME], data[CONF_PASSWORD]
    # )
    session = async_get_clientsession(hass)
    hub = PlaceholderHub(data[CONF_HOST], data[CONF_PORT], session)

    username = data.get(CONF_USERNAME)
    password = data.get(CONF_PASSWORD)

    if not await hub.authenticate(username, password):
        raise InvalidAuth
    # If you cannot connect:
    # throw CannotConnect
    # If the authentication is wrong:
    # InvalidAuth    host = data[CONF_HOST]
    port = data[CONF_PORT]
    if username and password:
        base_url = f"http://{username}:{password}@{host}:{port}"
    else:
        base_url = f"http://{host}:{port}"
    url = f"{base_url}/api/system/status"
    response = await session.get(url)
    content = await response.json()
    data[CONF_NAME] = content["host_name"] + " - " + content["interfaces"][0]["address"]
    # Return info that you want to store in the config entry.
    return {"name": content["host_name"]}


class FalconPiPlayerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Falcon Pi Player."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.discovered_host: str | None = None
        self.discovered_name: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["name"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        # Abort quick if the mac address is provided by discovery info
        if mac := discovery_info.properties.get(CONF_MAC):
            await self.async_set_unique_id(mac)
            self._abort_if_unique_id_configured(
                updates={CONF_HOST: discovery_info.host}
            )

        self.discovered_host = discovery_info.host

        # Try to get device info from the API
        try:
            url = f"http://{discovery_info.host}:{DEFAULT_PORT}/api/system/status"
            session = async_get_clientsession(self.hass)
            response = await session.get(url)
            if response.status != 200:
                return self.async_abort(reason="cannot_connect")
            content = await response.json()
        except aiohttp.ClientError:
            return self.async_abort(reason="cannot_connect")

        self.discovered_name = content.get("host_name", discovery_info.host)

        # Use MAC from properties or generate unique ID from host
        if not mac:
            await self.async_set_unique_id(discovery_info.host)
            self._abort_if_unique_id_configured(
                updates={CONF_HOST: discovery_info.host}
            )

        self.context["title_placeholders"] = {
            "name": self.discovered_name or "Falcon Pi Player"
        }
        self.context["configuration_url"] = f"http://{discovery_info.host}"
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by zeroconf."""
        if user_input is not None or not onboarding.async_is_onboarded(self.hass):
            return self.async_create_entry(
                title=self.discovered_device.info.name,
                data={
                    CONF_HOST: self.discovered_host,
                    CONF_PORT: DEFAULT_PORT,
                },
            )

        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={"name": self.discovered_device.info.name},
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""

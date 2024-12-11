"""Config flow for the Falcon Pi Player integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
import aiohttp

from homeassistant.components import onboarding, zeroconf
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME, CONF_HOST, CONF_PORT, CONF_PASSWORD, CONF_USERNAME, CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DEFAULT_PORT, DEFAULT_USERNAME, DEFAULT_PASSWORD, DOMAIN

_LOGGER = logging.getLogger(__name__)

# TODO adjust the data schema to the data that you need
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): str,
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
        vol.Required(CONF_PASSWORD, default=DEFAULT_PASSWORD): str,
    }
)

class PlaceholderHub:
    """Placeholder class to make tests pass.

    TODO Remove this placeholder class and replace with things from your PyPI package.
    """

    def __init__(self, host: str, port: str) -> None:
        """Initialize."""
        self.host = host
        self.port = port

    async def authenticate(self, username: str, password: str) -> bool:
        """Test if we can authenticate with the host."""
        self.username = username
        self.password = password
        self.base_url: str = (
            f"http://{self.username}:{self.password}@{self.host}:{self.port}"
        )
        url = f"{self.base_url}/api/system/status"
        async with aiohttp.ClientSession() as session:
            response = await session.head(url)
        if response.status == 200:
            return True
        return False


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

    hub = PlaceholderHub(data[CONF_HOST],data[CONF_PORT])

    if not await hub.authenticate(data[CONF_USERNAME], data[CONF_PASSWORD]):
        raise InvalidAuth

    # If you cannot connect:
    # throw CannotConnect
    # If the authentication is wrong:
    # InvalidAuth
    host = data[CONF_HOST]
    port = data[CONF_PORT]
    username = data[CONF_USERNAME]
    password = data[CONF_PASSWORD]
    base_url: str = (
        f"http://{username}:{password}@{host}:{port}"
    )
    url = f"{base_url}/api/system/status"
    async with aiohttp.ClientSession() as session:
        response = await session.get(url)
        content = await response.json()
    data[CONF_NAME] = content["host_name"]+" - "+content["interfaces"][0]["address"]
    # Return info that you want to store in the config entry.
    return {"name": content["host_name"]}


class ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Falcon Pi Player."""

    VERSION = 1

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
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        # Abort quick if the mac address is provided by discovery info
        if mac := discovery_info.properties.get(CONF_MAC):
            await self.async_set_unique_id(mac)
            self._abort_if_unique_id_configured(
                updates={CONF_HOST: discovery_info.host}
            )

        self.discovered_host = discovery_info.host
        try:
            self.discovered_device = await self._async_get_device(discovery_info.host)
        except Exception:
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(self.discovered_device.info.mac_address)
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.host})

        self.context.update(
            {
                "title_placeholders": {"name": self.discovered_device.info.name},
                "configuration_url": f"http://{discovery_info.host}",
            }
        )
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

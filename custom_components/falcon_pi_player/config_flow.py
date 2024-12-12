"""Config flow for the Falcon Pi Player integration."""

from __future__ import annotations
from aiohttp import ClientConnectorError, BasicAuth
import logging
from typing import Any
from yarl import URL
from aiohttp import ClientConnectorError
import voluptuous as vol
from homeassistant.helpers import aiohttp_client,
from homeassistant.components import onboarding, zeroconf
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from .fpp_client.fpp_client import FPPClient

from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_URL,
    CONF_VERIFY_SSL
)
from .fpp_client.exceptions import FPPAuthenticationException, FPPConnectionException, FPPResourceNotFound, FPPZeroConfException, FPPException
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import DEFAULT_PASSWORD, DEFAULT_URL, DEFAULT_USERNAME, DOMAIN, DEFAULT_VERIFY_SSL

_LOGGER = logging.getLogger(__name__)

# TODO: adjust the data schema to the data that you need
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL, default=DEFAULT_URL): cv.url,
        vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    }
)

async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    # TODO: validate the data can be used to set up a connection.

    # If your PyPI package is not built with async, pass your methods
    # to the executor:
    # await hass.async_add_executor_job(
    #     your_validate_func, data[CONF_USERNAME], data[CONF_PASSWORD]
    # )

    # Build Client Params
    auth: BasicAuth | None = None
    if data.get(CONF_USERNAME) and data.get(CONF_PASSWORD):
        auth = BasicAuth(data[CONF_USERNAME], data[CONF_PASSWORD])

    # Create Session
    session = async_get_clientsession(hass=hass, verify_ssl=data.get(CONF_VERIFY_SSL,True))

    # Setup Client
    fpp_client = FPPClient(url=data[CONF_URL], auth=auth, session=session)

    # Check if we can connect
    return await fpp_client.async_get_system_status()



class FPPConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Falcon Pi Player."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            url = URL(user_input[CONF_URL])
            user_input[CONF_URL] = url
            try:
                result = await validate_input(self.hass, user_input)
            except FPPAuthenticationException:
                errors = {"base": "invalid_auth"}
            except (ClientConnectorError, FPPConnectionException):
                errors = {"base": "cannot_connect"}
            except FPPZeroConfException:
                errors = {"base": "zeroconf_failed"}
            except FPPException:
                errors = {"base": "unknown"}
            else:
                return self.async_create_entry(title=result["name"], data=user_input)

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

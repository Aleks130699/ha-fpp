"""FPP API."""

from __future__ import annotations

from typing import Any

from aiohttp.client import ClientError, ClientSession, ClientTimeout
from aiohttp.helpers import BasicAuth
from yarl import URL

from .const import LOGGER, HTTPMethod
from .exceptions import (
    FPPAuthenticationException,
    FPPConnectionException,
    FPPException,
    FPPResourceNotFound,
)


class FPPClient:
    """Falcon Player Client."""

    _close_session = False

    def __init__(
        self,
        url: URL,
        request_timeout: float = 10,
        auth: BasicAuth | None = None,
        session: ClientSession | None = None,
        verify_ssl: bool = True,
    ) -> None:
        """Initialize the Falcon Player Client."""
        self._url: URL = url
        self._auth: BasicAuth | None = auth
        if session is None:
            session = ClientSession()
            self._close_session = True
        self._session = session
        self._verify_ssl = verify_ssl
        self._request_timeout = request_timeout
        self._headers: dict | None = None

    async def __aenter__(self):
        """Async enter."""
        return self

    async def __aexit__(self, *exc_info) -> None:
        """Async exit."""
        if self._session and self._close_session:
            await self._session.close()

    async def _async_request(
        self,
        command: str,
        params: dict | None = None,
        data: Any = None,
        method: HTTPMethod = HTTPMethod.GET,
    ) -> Any:
        """Send API request."""
        url: URL = self._url / command
        try:
            request = await self._session.request(
                method=method.value,
                url=url,
                params=params,
                data=data,
                headers=self._headers,
                timeout=ClientTimeout(self._request_timeout),
                ssl=self._verify_ssl,
            )

            if request.status >= 400:
                if request.status == 401:
                    raise FPPAuthenticationException(self, request)
                if request.status == 404:
                    raise FPPResourceNotFound(self, request)
                raise FPPConnectionException(
                    self,
                    f"Request for '{url}' failed with status code '{request.status}'",
                )

            _result: dict = await request.json()

        except ClientError as exception:
            raise FPPConnectionException(
                self,
                f"Request exception for '{url}' with - {exception}",
            ) from exception

        except TimeoutError as ex:
            raise FPPConnectionException(self, f"Request timeout for '{url}'") from ex

        except FPPAuthenticationException as ex:
            raise FPPAuthenticationException(self, ex) from ex

        except FPPConnectionException as ex:
            raise FPPConnectionException(self, ex) from ex

        except FPPException as ex:
            raise FPPException(self, ex) from ex

        except (Exception, BaseException) as ex:
            raise FPPException(self, ex) from ex
        else:
            LOGGER.debug("Requesting %s returned %s", url, _result)
            return _result

    async def async_get_system_status(self) -> dict[str, Any]:
        """Get information about system status."""

        return await self._async_request("system/status", method=HTTPMethod.GET)


class CannotConnectError(Exception):
    """Exception to indicate an error in connection."""

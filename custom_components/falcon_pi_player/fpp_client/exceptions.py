"""Exceptions for FPP Api Client."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiohttp import ClientResponse

    from .fpp_client import FPPClient


class FPPException(Exception):
    """Base arr exception."""

    def __init__(
        self,
        client: FPPClient | None = None,
        message: str | BaseException | ClientResponse | Exception = "",
    ) -> None:
        """Initialize."""
        super().__init__(str(message) if client is not None else message)


class FPPAuthenticationException(FPPException):
    """FPP authentication exception."""


class FPPConnectionException(FPPException):
    """FPP connection exception."""


class FPPResourceNotFound(FPPException):
    """FPP resource not found exception."""


class FPPWrongAppException(FPPException):
    """FPP wrong application exception."""


# TODO: Try zeroconfig setup.
class FPPZeroConfException(FPPException):
    """FPP Zero Configuration failed exception."""

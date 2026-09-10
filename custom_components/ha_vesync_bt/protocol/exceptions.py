"""Exceptions for the VeSync BLE protocol."""

class VeSyncProtocolError(Exception):
    """Base VeSync protocol error."""


class VeSyncConnectionError(VeSyncProtocolError):
    """Connection or GATT transport error."""


class VeSyncNotConnectedError(VeSyncConnectionError):
    """Operation requires an active BLE connection."""


class VeSyncProtocolTimeout(VeSyncProtocolError):
    """A protocol response timed out."""


class VeSyncProtocolResponseError(VeSyncProtocolError):
    """The device returned an invalid protocol response."""

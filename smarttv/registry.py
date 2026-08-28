"""Backend registry: picks who answers a command, with fallback.

A TV usually answers on more than one channel - a Samsung set takes both
HDMI-CEC and its own websocket - and each channel can do things the other
cannot.  The registry keeps the API honest: ask for a command, it finds the
first configured backend that is available *and* supports it.
"""

from __future__ import annotations

from .backends.base import BackendUnavailable, Capability, TVError, UnsupportedCommand
from .backends.cec import CECBackend
from .backends.dummy import DummyBackend
from .backends.samsung import SamsungBackend
from .backends.webos import WebOSBackend

BACKEND_CLASSES = {
    "cec": CECBackend,
    "samsung": SamsungBackend,
    "webos": WebOSBackend,
    "dummy": DummyBackend,
}

# Which capability each command needs, so fallback can skip backends that
# would only raise UnsupportedCommand.
COMMAND_CAPABILITY = {
    "power_on": Capability.POWER,
    "power_off": Capability.POWER,
    "power_status": Capability.POWER_STATUS,
    "volume": Capability.VOLUME,
    "send_key": Capability.KEYS,
    "set_source": Capability.SOURCE,
    "launch_app": Capability.APPS,
    "notify": Capability.NOTIFY,
    "raw": Capability.RAW,
}


class Registry:
    def __init__(self, backends):
        self.backends = list(backends)

    @classmethod
    def from_config(cls, tv_config, demo=False):
        if demo:
            return cls([DummyBackend()])
        backends = []
        for name in tv_config.get("order", []):
            settings = tv_config.get(name) or {}
            factory = BACKEND_CLASSES.get(name)
            if factory is None or not settings.get("enabled", False):
                continue
            backends.append(factory(settings))
        return cls(backends)

    # -- lookup -----------------------------------------------------------
    def get(self, name):
        for backend in self.backends:
            if backend.name == name:
                return backend
        return None

    def candidates(self, command):
        """Backends that could serve ``command``, in configured order."""
        capability = COMMAND_CAPABILITY.get(command)
        found = []
        for backend in self.backends:
            if capability and not backend.supports(capability):
                continue
            if not backend.available():
                continue
            found.append(backend)
        return found

    def active(self):
        for backend in self.backends:
            if backend.available():
                return backend
        return None

    def info(self):
        return [backend.info() for backend in self.backends]

    # -- dispatch ---------------------------------------------------------
    def call(self, command, *args, backend=None, **kwargs):
        """Run ``command`` on the first backend that can handle it.

        A backend that turns out to be unusable at call time (adapter
        unplugged, library missing) is skipped and the next one gets a go;
        a backend that answers and fails for a real reason stops the chain,
        because retrying elsewhere would hide the actual error.
        """
        if backend:
            target = self.get(backend)
            if target is None:
                raise TVError("unknown backend: %r" % (backend,))
            chain = [target]
        else:
            chain = self.candidates(command)
        if not chain:
            raise BackendUnavailable(
                "no backend available for %r (check config and cabling)" % command
            )
        last_error = None
        for target in chain:
            try:
                return getattr(target, command)(*args, **kwargs)
            except (BackendUnavailable, UnsupportedCommand) as exc:
                last_error = exc
                continue
        raise last_error

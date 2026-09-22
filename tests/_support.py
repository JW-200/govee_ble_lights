"""Test support: expose the component as an importable package.

The component directory is named ``govee-ble-lights`` (hyphens), which cannot
be imported as a normal Python name. These tests register it under an alias so
``from govee_ble_lights import models`` works.
"""

import enum
import importlib.util
import sys
import types
from pathlib import Path

PACKAGE_NAME = "govee_ble_lights"
COMPONENT_DIR = (
    Path(__file__).resolve().parent.parent / "custom_components" / "govee-ble-lights"
)


def ensure() -> None:
    """Register the package alias and add the component path (idempotent)."""
    _install_deps()
    if PACKAGE_NAME in sys.modules:
        return

    component = COMPONENT_DIR.resolve()
    sys.path.insert(0, str(component.parent))

    # Import as a real package so __init__.py runs and defines Hub.
    init_path = component / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        PACKAGE_NAME, init_path, submodule_search_locations=[str(component)]
    )
    package = importlib.util.module_from_spec(spec)
    sys.modules[PACKAGE_NAME] = package
    spec.loader.exec_module(package)


def _install_deps() -> None:
    """Stub third-party modules the component imports when they are not
    installed, so tests can run without a Home Assistant / BLE stack."""
    for name, attrs in (
        ("bleak", {"BleakClient": type("BleakClient", (), {})}),
        ("bleak_retry_connector", {"establish_connection": lambda *a, **k: None}),
    ):
        if name in sys.modules:
            continue
        try:
            __import__(name)
        except ImportError:
            module = types.ModuleType(name)
            for attr, value in attrs.items():
                setattr(module, attr, value)
            sys.modules[name] = module

    _install_homeassistant_stubs()


def _install_homeassistant_stubs() -> None:
    """Stub the Home Assistant modules ``light.py`` imports when HA is absent."""
    if "homeassistant" in sys.modules:
        return
    try:
        __import__("homeassistant")
        return
    except ImportError:
        pass

    class LightEntityFeature(enum.IntFlag):
        TRANSITION = 1
        EFFECT = 2

    class ColorMode(enum.Enum):
        RGB = "rgb"

    class LightEntity:
        hass = None

        def async_write_ha_state(self) -> None:
            pass

    class DeviceInfo(dict):
        pass

    modules = {
        "homeassistant": {},
        "homeassistant.components": {},
        "homeassistant.components.bluetooth": {
            "async_last_service_info": lambda *a, **k: None,
            "async_ble_device_from_address": lambda *a, **k: None,
        },
        "homeassistant.components.light": {
            "ATTR_BRIGHTNESS": "brightness",
            "ATTR_RGB_COLOR": "rgb_color",
            "ATTR_EFFECT": "effect",
            "ATTR_TRANSITION": "transition",
            "EFFECT_OFF": "None",
            "LightEntity": LightEntity,
            "LightEntityFeature": LightEntityFeature,
            "ColorMode": ColorMode,
        },
        "homeassistant.config_entries": {"ConfigEntry": type("ConfigEntry", (), {})},
        "homeassistant.const": {"MAJOR_VERSION": 2026, "MINOR_VERSION": 1},
        "homeassistant.core": {"HomeAssistant": type("HomeAssistant", (), {})},
        "homeassistant.exceptions": {
            "ConfigEntryNotReady": type("ConfigEntryNotReady", (Exception,), {})
        },
        "homeassistant.helpers": {},
        "homeassistant.helpers.entity": {"DeviceInfo": DeviceInfo},
    }
    for name, attrs in modules.items():
        module = types.ModuleType(name)
        for attr, value in attrs.items():
            setattr(module, attr, value)
        sys.modules[name] = module

    # Wire submodules onto their parents so ``from a.b import c`` resolves.
    for name in modules:
        parent, _, child = name.rpartition(".")
        if parent:
            setattr(sys.modules[parent], child, sys.modules[name])

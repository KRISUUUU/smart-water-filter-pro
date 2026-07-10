"""Constants for Smart Water Filter integration."""

DOMAIN = "smart_water_filter"
STORAGE_VERSION = 5

CONF_SOURCE_SENSOR = "source_sensor"
CONF_SOURCE_TYPE = "source_type"
CONF_PULSES_PER_LITER = "pulses_per_liter"
CONF_INITIAL_CAPACITY = "initial_capacity"

SOURCE_TYPE_PULSES = "pulses"
SOURCE_TYPE_LITERS = "liters"

DEFAULT_PULSES_PER_LITER = 450.0
DEFAULT_CAPACITY = 3000.0

FLOW_MIN_THRESHOLD = 0.01
EMA_ALPHA = 0.2
MAX_EVENTS = 500

def localize_stage_name(hass, stage_name: str) -> str:
    """Localize stage names if they match default presets."""
    if not hass:
        return stage_name
    lang = getattr(hass.config, "language", "en")
    if lang == "pl":
        mapping = {
            "Carbon Filter 1": "węglowy 1",
            "Carbon Filter 2": "węglowy 2",
            "Sediment Filter 5um": "sedymentacyjny 5um",
            "Sediment Filter 10um": "sedymentacyjny 10um",
            "Sediment Filter 20um": "sedymentacyjny 20um",
            "RO Membrane": "membrana ro",
            "Carbon Filter": "węglowy",
            "Capillary Filter": "membrana",
            "Sediment Filter": "sedymentacyjny",
            "Filter Stage": "Stopień filtracji",
            "carbon": "węglowy",
            "capillary": "kapilarny",
            "sediment": "sedymentacyjny",
            "custom": "własny",
        }
        return mapping.get(stage_name, stage_name)
    return stage_name

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

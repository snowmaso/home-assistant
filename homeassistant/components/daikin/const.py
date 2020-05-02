"""Constants for Daikin."""
from homeassistant.const import CONF_ICON, CONF_NAME, CONF_TYPE

ATTR_TARGET_TEMPERATURE = "target_temperature"
ATTR_INSIDE_TEMPERATURE = "inside_temperature"
ATTR_OUTSIDE_TEMPERATURE = "outside_temperature"
ATTR_DAY_ENERGY = 'day_energy'

ATTR_STATE_ON = "on"
ATTR_STATE_OFF = "off"

SENSOR_TYPE_TEMPERATURE = "temperature"
SENSOR_TYPE_ENERGY = 'energy'

SENSOR_TYPES = {
    ATTR_INSIDE_TEMPERATURE: {
        CONF_NAME: "Inside Temperature",
        CONF_ICON: "mdi:thermometer",
        CONF_TYPE: SENSOR_TYPE_TEMPERATURE,
    },
    ATTR_OUTSIDE_TEMPERATURE: {
        CONF_NAME: "Outside Temperature",
        CONF_ICON: "mdi:thermometer",
        CONF_TYPE: SENSOR_TYPE_TEMPERATURE,
    },
    ATTR_DAY_ENERGY: {
        CONF_NAME: 'Day Energy',
        CONF_ICON: 'mdi:power-plug',
        CONF_TYPE: SENSOR_TYPE_ENERGY
    }
}

KEY_MAC = "mac"
KEY_IP = "ip"

TIMEOUT = 60

"""Support for displaying weather info from Ecobee API."""
from datetime import datetime

from pyecobee.const import ECOBEE_STATE_UNKNOWN

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_SPEED,
    WeatherEntity,
)
from homeassistant.const import TEMP_FAHRENHEIT

from .const import DOMAIN

ATTR_FORECAST_TEMP_HIGH = "temphigh"
ATTR_FORECAST_PRESSURE = "pressure"
ATTR_FORECAST_VISIBILITY = "visibility"
ATTR_FORECAST_HUMIDITY = "humidity"


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Old way of setting up the ecobee weather platform."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the ecobee weather platform."""
    data = hass.data[DOMAIN]
    dev = list()
    for index in range(len(data.ecobee.thermostats)):
        thermostat = data.ecobee.get_thermostat(index)
        if "weather" in thermostat:
            dev.append(EcobeeWeather(data, thermostat["name"], index))

    async_add_entities(dev, True)


class EcobeeWeather(WeatherEntity):
    """Representation of Ecobee weather data."""

    def __init__(self, data, name, index):
        """Initialize the Ecobee weather platform."""
        self.data = data
        self._name = name
        self._index = index
        self.weather = None

    def get_forecast(self, index, param):
        """Retrieve forecast parameter."""
        try:
            forecast = self.weather["forecasts"][index]
            return forecast[param]
        except (ValueError, IndexError, KeyError):
            raise ValueError

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique identifier for the weather platform."""
        return self.data.ecobee.get_thermostat(self._index)["identifier"]

    @property
    def condition(self):
        """Return the current condition."""
        try:
            return self.get_forecast(0, "condition")
        except ValueError:
            return None

    @property
    def temperature(self):
        """Return the temperature."""
        try:
            return float(self.get_forecast(0, "temperature")) / 10
        except ValueError:
            return None

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_FAHRENHEIT

    @property
    def pressure(self):
        """Return the pressure."""
        try:
            return int(self.get_forecast(0, "pressure"))
        except ValueError:
            return None

    @property
    def humidity(self):
        """Return the humidity."""
        try:
            return int(self.get_forecast(0, "relativeHumidity"))
        except ValueError:
            return None

    @property
    def visibility(self):
        """Return the visibility."""
        try:
            return int(self.get_forecast(0, "visibility"))
        except ValueError:
            return None

    @property
    def wind_speed(self):
        """Return the wind speed."""
        try:
            return int(self.get_forecast(0, "windSpeed"))
        except ValueError:
            return None

    @property
    def wind_bearing(self):
        """Return the wind direction."""
        try:
            return int(self.get_forecast(0, "windBearing"))
        except ValueError:
            return None

    @property
    def attribution(self):
        """Return the attribution."""
        if self.weather:
            station = self.weather.get("weatherStation", "UNKNOWN")
            time = self.weather.get("timestamp", "UNKNOWN")
            return f"Ecobee weather provided by {station} at {time}"
        return None

    @property
    def forecast(self):
        """Return the forecast array."""
        try:
            forecasts = []
            for day in self.weather["forecasts"]:
                date_time = datetime.strptime(
                    day["dateTime"], "%Y-%m-%d %H:%M:%S"
                ).isoformat()
                forecast = {
                    ATTR_FORECAST_TIME: date_time,
                    ATTR_FORECAST_CONDITION: day["condition"],
                    ATTR_FORECAST_TEMP: float(day["tempHigh"]) / 10,
                }
                if day["tempHigh"] == ECOBEE_STATE_UNKNOWN:
                    break
                if day["tempLow"] != ECOBEE_STATE_UNKNOWN:
                    forecast[ATTR_FORECAST_TEMP_LOW] = float(day["tempLow"]) / 10
                if day["pressure"] != ECOBEE_STATE_UNKNOWN:
                    forecast[ATTR_FORECAST_PRESSURE] = int(day["pressure"])
                if day["windSpeed"] != ECOBEE_STATE_UNKNOWN:
                    forecast[ATTR_FORECAST_WIND_SPEED] = int(day["windSpeed"])
                if day["visibility"] != ECOBEE_STATE_UNKNOWN:
                    forecast[ATTR_FORECAST_WIND_SPEED] = int(day["visibility"])
                if day["relativeHumidity"] != ECOBEE_STATE_UNKNOWN:
                    forecast[ATTR_FORECAST_HUMIDITY] = int(day["relativeHumidity"])
                forecasts.append(forecast)
            return forecasts
        except (ValueError, IndexError, KeyError):
            return None

    async def async_update(self):
        """Get the latest weather data."""
        await self.data.update()
        thermostat = self.data.ecobee.get_thermostat(self._index)
        self.weather = thermostat.get("weather", None)

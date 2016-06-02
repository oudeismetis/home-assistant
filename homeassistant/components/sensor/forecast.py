"""
Support for Forecast.io weather service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.forecast/
"""
import logging
from datetime import timedelta

from homeassistant.const import CONF_API_KEY, TEMP_CELSIUS
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['python-forecastio==1.3.4']
_LOGGER = logging.getLogger(__name__)

# Sensor types are defined like so:
# Name, si unit, us unit, ca unit, uk unit, uk2 unit
SENSOR_TYPES = {
    'summary': ['Summary', None, None, None, None, None],
    'minutely_summary': ['Minutely Summary', None, None, None, None, None],
    'hourly_summary': ['Hourly Summary', None, None, None, None, None],
    'daily_summary': ['Daily Summary', None, None, None, None, None],
    'icon': ['Icon', None, None, None, None, None],
    'nearest_storm_distance': ['Nearest Storm Distance',
                               'km', 'm', 'km', 'km', 'm'],
    'nearest_storm_bearing': ['Nearest Storm Bearing',
                              '°', '°', '°', '°', '°'],
    'precip_type': ['Precip', None, None, None, None, None],
    'precip_intensity': ['Precip Intensity', 'mm', 'in', 'mm', 'mm', 'mm'],
    'precip_probability': ['Precip Probability', '%', '%', '%', '%', '%'],
    'temperature': ['Temperature', '°C', '°F', '°C', '°C', '°C'],
    'apparent_temperature': ['Apparent Temperature',
                             '°C', '°F', '°C', '°C', '°C'],
    'dew_point': ['Dew point', '°C', '°F', '°C', '°C', '°C'],
    'wind_speed': ['Wind Speed', 'm/s', 'mph', 'km/h', 'mph', 'mph'],
    'wind_bearing': ['Wind Bearing', '°', '°', '°', '°', '°'],
    'cloud_cover': ['Cloud Coverage', '%', '%', '%', '%', '%'],
    'humidity': ['Humidity', '%', '%', '%', '%', '%'],
    'pressure': ['Pressure', 'mBar', 'mBar', 'mBar', 'mBar', 'mBar'],
    'visibility': ['Visibility', 'km', 'm', 'km', 'km', 'm'],
    'ozone': ['Ozone', 'DU', 'DU', 'DU', 'DU', 'DU'],
}

# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=120)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Forecast.io sensor."""

    api_key = config.get(CONF_API_KEY, None)
    if None in (hass.config.latitude, hass.config.longitude, api_key):
        _LOGGER.error("Latitude, longitude, or API key missing from config")
        return False

    if 'units' in config:
        units = config['units']
    elif hass.config.temperature_unit == TEMP_CELSIUS:
        units = 'si'
    else:
        units = 'us'

    sensor_data = ForeCastData(api_key, hass.config.latitude,
                               hass.config.longitude, units)

    sensors = []
    for variable in config['monitored_conditions']:
        print('looking for: ', variable)
        if variable not in SENSOR_TYPES:
            _LOGGER.error('Sensor type: "%s" does not exist', variable)
            return False
        else:
            sensor = ForeCastSensor(sensor_data, variable)
            if not sensor.state:
                _LOGGER.error(
                    "Connection error "
                    "Please check your settings for Forecast.io.")
                return False
            sensors.append(sensor)

    add_devices(sensors)


class ForeCastSensor(Entity):
    """Implementation of a Forecast.io sensor."""

    def __init__(self, data_sdk, sensor_type):
        """Initialize the sensor."""

        self.sdk = data_sdk

        # self.data = None
        self._unit_system = None
        self._unit_of_measurement = None
        self.data_currently = None
        self.data_minutely = None
        self.data_hourly = None
        self.data_daily = None

        self.client_name = 'Weather'
        self._name = SENSOR_TYPES[sensor_type][0]
        self.type = sensor_type
        self._state = None

        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self.client_name, self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def unit_system(self):
        """Return the unit system of this entity."""
        return self._unit_system

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from Forecast.io and updates the states."""

        import forecastio
        print('Inside update for forecast')

        self.sdk.update()
        self.update_unit_of_measure()

        try:
            if self.type == 'minutely_summary':
                self.update_minutely()
                self._state = self.data_minutely.summary
                return

            elif self.type == 'hourly_summary':
                self.update_hourly()
                self._state = self.data_hourly.summary
                return

            elif self.type == 'daily_summary':
                self.update_daily()
                self._state = self.data_daily.summary
                return

        except forecastio.utils.PropertyUnavailable:
            return

        self.update_currently()
        self.update_state(self.data_currently)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update_currently(self):
        """Update currently data."""
        self.data_currently = self.sdk.data.currently()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update_minutely(self):
        """Update minutely data."""
        self.data_minutely = self.sdk.data.minutely()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update_hourly(self):
        """Update hourly data."""
        self.data_hourly = self.sdk.data.hourly()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update_daily(self):
        """Update daily data."""
        self.data_daily = self.sdk.data.daily()

    def update_unit_of_measure(self):
        """Convert received units to ones we understand."""
        unit_system = self.sdk.data.json['flags']['units']
        if unit_system == 'si':
            self._unit_of_measurement = SENSOR_TYPES[self.type][1]
        elif unit_system == 'us':
            self._unit_of_measurement = SENSOR_TYPES[self.type][2]
        elif unit_system == 'ca':
            self._unit_of_measurement = SENSOR_TYPES[self.type][3]
        elif unit_system == 'uk':
            self._unit_of_measurement = SENSOR_TYPES[self.type][4]
        elif unit_system == 'uk2':
            self._unit_of_measurement = SENSOR_TYPES[self.type][5]

    def update_state(self, current_data):
        """Update the current state of the sensor"""
        import forecastio
        try:
            if self.type == 'summary':
                self._state = current_data.summary
            elif self.type == 'icon':
                self._state = current_data.icon
            elif self.type == 'nearest_storm_distance':
                self._state = current_data.nearestStormDistance
            elif self.type == 'nearest_storm_bearing':
                self._state = current_data.nearestStormBearing
            elif self.type == 'precip_intensity':
                self._state = current_data.precipIntensity
            elif self.type == 'precip_type':
                self._state = current_data.precipType
            elif self.type == 'precip_probability':
                self._state = round(current_data.precipProbability * 100, 1)
            elif self.type == 'dew_point':
                self._state = round(current_data.dewPoint, 1)
            elif self.type == 'temperature':
                self._state = round(current_data.temperature, 1)
            elif self.type == 'apparent_temperature':
                self._state = round(current_data.apparentTemperature, 1)
            elif self.type == 'wind_speed':
                self._state = current_data.windSpeed
            elif self.type == 'wind_bearing':
                self._state = current_data.windBearing
            elif self.type == 'cloud_cover':
                self._state = round(current_data.cloudCover * 100, 1)
            elif self.type == 'humidity':
                self._state = round(current_data.humidity * 100, 1)
            elif self.type == 'pressure':
                self._state = round(current_data.pressure, 1)
            elif self.type == 'visibility':
                self._state = current_data.visibility
            elif self.type == 'ozone':
                self._state = round(current_data.ozone, 1)
        except forecastio.utils.PropertyUnavailable:
            pass


class ForeCastData(object):
    """Gets the latest data from Forecast.io."""

    def __init__(self, api_key, latitude, longitude, units):
        """Initialize the data object."""
        self._api_key = api_key
        self.latitude = latitude
        self.longitude = longitude
        self.units = units
        self.data = None

        self.update()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from Forecast.io and updates the states."""
        import forecastio

        self.data = forecastio.load_forecast(self._api_key,
                                             self.latitude,
                                             self.longitude,
                                             units=self.units)

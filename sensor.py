import logging
from datetime import timedelta
from homeassistant.components.sensor import ENTITY_ID_FORMAT
from custom_components.shelly_cloud import (DOMAIN, ShellyCloudEntity)

# Setting log
_LOGGER = logging.getLogger('shelly_cloud_sensor')
_LOGGER.setLevel(logging.DEBUG)

# define the HA scan for sensor
SCAN_INTERVAL = timedelta(seconds=10)

shelly_cloud_SENSORS_MAP = {
    'bat': {'eid': 'battery', 'uom': '%', 'icon': 'mdi:battery', 'factor': 1, 'decimals': 2},
    'hum': {'eid': 'humidity', 'uom': '%', 'icon': 'mdi:water-percent', 'factor': 1, 'decimals': 2},
    'tmp':  {'eid': 'temperature', 'uom': '°C', 'icon': 'mdi:temperature-celsius', 'factor': 1, 'decimals': 2},
    'power':  {'eid': 'power', 'uom': 'W', 'icon': 'mdi:flash-outline', 'factor': 0.001,'decimals': 2},
    'current': {'eid': 'current', 'uom': 'A', 'icon': 'mdi:current-ac', 'factor': 0.001,'decimals': 2},
    'voltage': {'eid': 'voltage', 'uom': 'V', 'icon': 'mdi:power-plug', 'factor': 0.1,  'decimals': 2},
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):

    _LOGGER.debug('async_setup_platform >>> started')

    if discovery_info is None:
        _LOGGER.warning('async_setup_platform >>> discovery_info is None')
        pass
    else:
        ha_entities = []

        # get shelly device id
        shelly_cloud_device_id = discovery_info.get('shelly_cloud_device_id')
        # check if shelly is in the device list
        if shelly_cloud_device_id not in hass.data[DOMAIN].devices:
            # error: the device id is not in the list...
            keys = str(hass.data[DOMAIN].devices.keys())
            _LOGGER.error('device id ' + shelly_cloud_device_id + ' is not in ' + keys)
        else:
            # get the shelly_cloud device info
            shelly_cloud_device_info = hass.data[DOMAIN].devices[shelly_cloud_device_id]
            # get the shelly_cloud device status
            shelly_cloud_device_status = hass.data[DOMAIN].devices_status[shelly_cloud_device_id]
            # get the shelly_cloud device name
            shelly_cloud_device_name = shelly_cloud_device_info['name']
            for shelly_cloud_sensor_name in shelly_cloud_SENSORS_MAP:
                if shelly_cloud_sensor_name in shelly_cloud_device_status:
                    _LOGGER.info('registering sensor: '
                                 'id: ' + shelly_cloud_device_id + ', ' +
                                 'name: ' + shelly_cloud_device_name + ', ' +
                                 'sensor: ' + shelly_cloud_sensor_name)
                    # creiamo una entità Home Assistant di tipo ShellyCloudSensorEntity
                    sensor = ShellyCloudSensorEntity(hass,
                                                     shelly_cloud_device_id,
                                                     shelly_cloud_device_name,
                                                     shelly_cloud_sensor_name)
                    # aggiungiamola alle entità da aggiungere
                    ha_entities.append(sensor)

        if len(ha_entities) > 0:
            async_add_entities(ha_entities, update_before_add=False)

    _LOGGER.debug('async_setup_platform <<< terminated')

    return True


class ShellyCloudSensorEntity(ShellyCloudEntity):

    def __init__(self, hass, shelly_cloud_device_id, shelly_cloud_device_name, shelly_cloud_sensor_name):
        # attributes
        self._value = 0
        self._shelly_cloud_sensor_name = shelly_cloud_sensor_name

        # naming
        shelly_cloud_sensor_id = "{}_{}_{}".format(DOMAIN,
                                                   shelly_cloud_device_id,
                                                   shelly_cloud_SENSORS_MAP[shelly_cloud_sensor_name]['eid'])
        shelly_cloud_entity_id = ENTITY_ID_FORMAT.format(shelly_cloud_sensor_id)

        # init ShellyCloudEntity
        shelly_cloud_device_online = hass.data[DOMAIN].get_device_availability(shelly_cloud_device_id)
        super().__init__(hass,
                         shelly_cloud_device_id,
                         shelly_cloud_device_name,
                         shelly_cloud_entity_id,
                         shelly_cloud_sensor_name,
                         shelly_cloud_device_online)

    async def async_update(self):
        id = self._shelly_cloud_device_id
        sensor = self._shelly_cloud_sensor_name
        self._value = self.hass.data[DOMAIN].devices_status[id][sensor]['value']
        _LOGGER.debug(self._shelly_cloud_device_name + ' >>> ' +
                      self._shelly_cloud_entity_name + ' >>> async_update() >>> ' +
                      str(self._value))
        return True

    @property
    def unit_of_measurement(self):
        uom = shelly_cloud_SENSORS_MAP[self._shelly_cloud_sensor_name]['uom']
        _LOGGER.debug(self._shelly_cloud_device_name + ' >>> ' +
                      self._shelly_cloud_entity_name + ' >>> unit_of_measurement() >>> ' +
                      uom)
        # Return the unit of measurement.
        return uom

    @property
    def icon(self):
        icon = shelly_cloud_SENSORS_MAP[self._shelly_cloud_sensor_name]['icon']
        _LOGGER.debug(self._shelly_cloud_device_name + ' >>> ' +
                      self._shelly_cloud_entity_name + ' >>> icon() >>> ' +
                      str(icon))
        # Return the icon.
        return icon

    @property
    def state(self):
        f = shelly_cloud_SENSORS_MAP[self._shelly_cloud_sensor_name]['factor']
        formatted_value = '{:.{d}f}'.format(self._value*f, d=shelly_cloud_SENSORS_MAP[self._shelly_cloud_sensor_name]['decimals'])
        _LOGGER.debug(self._shelly_cloud_device_name + ' >>> ' +
                      self._shelly_cloud_entity_name + ' >>> state() >>> ' +
                      formatted_value)
        return formatted_value

import logging
from datetime import timedelta
from homeassistant.components.switch import ENTITY_ID_FORMAT, SwitchDevice
from custom_components.shelly_cloud import (DOMAIN, ShellyCloudEntity)

# Setting log
_LOGGER = logging.getLogger('shelly_cloud_switch')
_LOGGER.setLevel(logging.DEBUG)

# define the HA scan for switch
SCAN_INTERVAL = timedelta(seconds=5)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):

    _LOGGER.debug('async_setup_platform >>> started')

    if discovery_info is None:
        _LOGGER.warning('async_setup_platform >>> discovery_info is None')
        pass
    else:
        ha_entities = []

        shelly_cloud_device_id = discovery_info.get('shelly_cloud_device_id')
        if shelly_cloud_device_id not in hass.data[DOMAIN].devices:
            keys = str(hass.data[DOMAIN].devices.keys())
            _LOGGER.error('uuid ' + shelly_cloud_device_id + ' is not in ' + keys)
        else:
            # get the shelly_cloud plug
            shelly_cloud_device = hass.data[DOMAIN].devices[shelly_cloud_device_id]
            # get the shelly_cloud device name
            shelly_cloud_device_name = shelly_cloud_device['name']
            # num of channels...
            channels = shelly_cloud_device['channels_count']
            for shelly_cloud_switch_channel in range(0, channels):
                suffix = ''
                if channels > 0:
                    suffix = '_'+str(shelly_cloud_switch_channel)                
                # creiamo una entità Home Assistant di tipo shelly_cloudSwitchEntity
                switch = ShellyCloudSwitchEntity(hass,
                                                 shelly_cloud_device_id,
                                                 shelly_cloud_device_name,
                                                 shelly_cloud_switch_channel,
                                                 suffix)
                # aggiungiamola alle entità da aggiungere
                ha_entities.append(switch)

        if len(ha_entities) > 0:
            async_add_entities(ha_entities, update_before_add=False)

    _LOGGER.debug('async_setup_platform() <<< terminated')

    return True


class ShellyCloudSwitchEntity(ShellyCloudEntity, SwitchDevice):

    def __init__(self, hass, shelly_cloud_device_id, shelly_cloud_device_name, shelly_cloud_switch_channel, suffix):

        # attributes
        self._is_on = False
        self._shelly_cloud_switch_channel = shelly_cloud_switch_channel
        self._shelly_cloud_plug = hass.data[DOMAIN].shelly_cloud_switch_by_id[shelly_cloud_device_id]

        # add entity to the shelly_cloud_plug
        shelly_cloud_device = self._shelly_cloud_plug.device
        shelly_cloud_device_online = shelly_cloud_device.online
        self._shelly_cloud_plug.switch_states[shelly_cloud_switch_channel] = {
            'available':  shelly_cloud_device_online,
            'is_on': self._is_on,
            }

        # naming
        shelly_cloud_switch_name = str(shelly_cloud_switch_channel)
        shelly_cloud_switch_id = "{}_{}{}".format(DOMAIN, shelly_cloud_device_id, suffix)
        shelly_cloud_entity_id = ENTITY_ID_FORMAT.format(shelly_cloud_switch_id)
        _LOGGER.debug(shelly_cloud_device_name + ' >>> ' + shelly_cloud_switch_name + ' >>> __init__()')        

        # init shelly_cloudEntity
        super().__init__(hass,
                         shelly_cloud_device_id,
                         shelly_cloud_device_name,
                         shelly_cloud_entity_id,
                         shelly_cloud_switch_name,
                         shelly_cloud_device_online)

    async def async_execute_switch_and_set_status(self):
        _LOGGER.debug(self._shelly_cloud_device_name + ' >>> ' + self._shelly_cloud_entity_name +
                      ' >>> async_execute_switch_and_set_status()')
        shelly_cloud_plug = self.hass.data[DOMAIN].shelly_cloud_switch_by_id[self._shelly_cloud_device_id]
        shelly_cloud_device = shelly_cloud_plug.device
        if shelly_cloud_device is None:
            _LOGGER.error(self._shelly_cloud_device_name + ' is None')
            return False
        elif not shelly_cloud_device.online:
            _LOGGER.warning(self._shelly_cloud_device_name + ' is not online')
            shelly_cloud_plug.switch_states[self._shelly_cloud_switch_channel]['available'] = False
            return False
        else:
            if self._is_on:
                shelly_cloud_device.turn_on_channel(self._shelly_cloud_switch_channel)
            else:
                shelly_cloud_device.turn_off_channel(self._shelly_cloud_switch_channel)
            shelly_cloud_plug.switch_states[self._shelly_cloud_switch_channel]['is_on'] = self._is_on
        return True

    async def async_turn_on(self):
        self._is_on = True
        _LOGGER.info(self._shelly_cloud_device_name + ' >>> ' +
                     self._shelly_cloud_entity_name + ' >>> async_turn_on()')
        return self.hass.async_add_job(self.async_execute_switch_and_set_status)

    async def async_turn_off(self):
        self._is_on = False
        _LOGGER.info(self._shelly_cloud_device_name + ' >>> ' +
                     self._shelly_cloud_entity_name + ' >>> async_turn_off()')
        return self.hass.async_add_job(self.async_execute_switch_and_set_status)

    async def async_update(self):
        _LOGGER.debug(self._shelly_cloud_device_name + ' >>> ' +
                      self._shelly_cloud_entity_name + ' >>> async_update()')
        updated_is_on = self._shelly_cloud_plug.switch_states[self._shelly_cloud_switch_channel]['is_on']
        if updated_is_on != self._is_on:
            _LOGGER.info(self._shelly_cloud_device_name + ' >>> ' +
                         self._shelly_cloud_entity_name + ' >>> switching from ' +
                         str(self._is_on) + ' to ' +
                         str(updated_is_on))
        self._is_on = updated_is_on
        self._available = self._shelly_cloud_plug.switch_states[self._shelly_cloud_switch_channel]['available']
        return True

    @property
    def name(self):
        """Name of the device."""
        _LOGGER.debug(self._shelly_cloud_device_name + ' >>> ' +
                      self._shelly_cloud_entity_name + ' >>> name() >>> ' +
                      self._shelly_cloud_device_name)
        return self._shelly_cloud_device_name

    @property
    def is_on(self):
        _LOGGER.debug(self._shelly_cloud_device_name+' >>> ' +
                      self._shelly_cloud_device_name + ' >>> is_on() >>> ' +
                      str(self._is_on))
        return self._is_on


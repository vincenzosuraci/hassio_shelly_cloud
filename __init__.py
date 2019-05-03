from datetime import timedelta
import logging
import voluptuous as vol
import requests
import hashlib

from homeassistant.const import (CONF_USERNAME, CONF_PASSWORD, CONF_SCAN_INTERVAL)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

""" Setting log """
_LOGGER = logging.getLogger('shelly_cloud_init')
_LOGGER.setLevel(logging.DEBUG)

""" This is needed to ensure shelly_cloud_iot library is always updated """
""" Ref: https://developers.home-assistant.io/docs/en/creating_integration_manifest.html"""
REQUIREMENTS = []

""" This is needed, it impact on the name to be called in configurations.yaml """
""" Ref: https://developers.home-assistant.io/docs/en/creating_integration_manifest.html"""
DOMAIN = 'shelly_cloud'

SIGNAL_DELETE_ENTITY = 'shelly_cloud_delete'
SIGNAL_UPDATE_ENTITY = 'shelly_cloud_update'

HA_SWITCH = 'switch'

DEFAULT_SCAN_INTERVAL = timedelta(seconds=10)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,

        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.time_period,
    })
}, extra=vol.ALLOW_EXTRA)


# ----------------------------------------------------------------------------------------------------------------------
#
# ASYNC SETUP
#
# ----------------------------------------------------------------------------------------------------------------------


async def async_setup(hass, config):

    _LOGGER.debug('async_setup() >>> STARTED')

    # create ShellyCloudPlatform instance
    hass.data[DOMAIN] = ShellyCloudPlatform(hass, config)

    _LOGGER.debug('async_setup() <<< TERMINATED')

    return True

# ----------------------------------------------------------------------------------------------------------------------
#
# Shelly Cloud Platform
#
# ----------------------------------------------------------------------------------------------------------------------


class ShellyCloudPlatform:

    def __init__(self, hass, config):

        # home assistant
        self._hass = hass
        self._config = config

        # Shelly Cloud credentials
        self._username = config[DOMAIN][CONF_USERNAME]
        self._password = config[DOMAIN][CONF_PASSWORD]

        # do login and get data (False otherwise...)
        self._data = self.login()

        # if we have data, get device list
        if self._data:
            self.devices = self.get_device_list()
            if self.devices:
                self.devices_status = self.get_devices_status()
                _LOGGER.debug(self._devices_status)

        # switch discovery
        self.discover_switches()

    def login(self):
        # login url
        url = 'https://api.shelly.cloud/auth/login'
        # get e-mail
        email = self._username
        # get sha1 password
        sha1_password = hashlib.sha1(self._password.encode('utf-8')).hexdigest()
        # set POST https params
        params = {'email': email, 'password': sha1_password}
        # get response to POST request
        response = requests.post(url, params)
        # get dict of POST response
        data = response.json()
        # check if everything is Ok
        if data['isok']:
            # login was succesful!
            return data['data']
        else:
            # print errors
            errors = data['errors']
            for error_title, error_message in errors.items():
                _LOGGER.error(error_title + ' : ' + error_message)
        return False

    def get_device_list(self):
        # device list url
        url = 'https://shelly-2-eu.shelly.cloud/interface/device/list'
        # set POST https params
        params = {'Authorization': 'Bearer ' + self._data['token']}
        # get response
        response = requests.post(url, params)
        # get dict of POST response
        data = response.json()
        # check if everything is Ok
        if data['isok']:
            # get_device_list was succesful!
            return data['data']['devices']
        else:
            # print errors
            errors = data['errors']
            for error_title, error_message in errors.items():
                _LOGGER.error(error_title + ' : ' + error_message)
        return False

    def get_devices_status(self):
        # device list url
        url = 'https://shelly-2-eu.shelly.cloud/device/all_status'
        # set POST https params
        params = {'Authorization': 'Bearer ' + self._data['token']}
        # get response
        response = requests.post(url, params)
        # get dict of POST response
        data = response.json()
        # check if everything is Ok
        if data['isok']:
            # get_devices_status was succesful!
            return data['data']['devices_status']
        else:
            # print errors
            errors = data['errors']
            for error_title, error_message in errors.items():
                _LOGGER.error(error_title + ' : ' + error_message)
        return False

    def set_device_channel(self, id, channel, turn):
        # control url
        url = 'https://shelly-2-eu.shelly.cloud/device/relay/control'
        # set POST https params
        params = {'id': id, 'channel': channel, 'turn': turn, 'Authorization': 'Bearer ' + self._data['token']}
        # get response
        response = requests.post(url, params)
        # get dict of POST response
        data = response.json()
        # check if everything is Ok
        if data['isok']:
            # set_device_channel was succesful!
            return True
        else:
            # print errors
            errors = data['errors']
            for error_title, error_message in errors.items():
                _LOGGER.error(error_title + ' : ' + error_message)
        return False

    def discover_switches(self):
        for device_id, device_info in self.devices:
            if 'switches_discovered' not in device_info:
                device_info['switches_discovered'] = True
                self._hass.async_create_task(
                    discovery.async_load_platform(self._hass,
                                                  HA_SWITCH,
                                                  DOMAIN,
                                                  {'shelly_cloud_device_id': device_id},
                                                  self._config))

# ----------------------------------------------------------------------------------------------------------------------
#
# SHELLY CLOUD ENTITY
#
# ----------------------------------------------------------------------------------------------------------------------


class ShellyCloudEntity(Entity):
    # Shelly Cloud entity ( sensor / switch )

    def __init__(self,
                 hass,
                 shelly_cloud_device_id,
                 shelly_cloud_device_name,
                 shelly_cloud_entity_id,
                 shelly_cloud_entity_name,
                 available):

        self.hass = hass
        self.entity_id = shelly_cloud_entity_id

        """Register the physical shelly_cloud device id"""
        self._shelly_cloud_device_id = shelly_cloud_device_id
        self._shelly_cloud_entity_name = shelly_cloud_entity_name
        self._shelly_cloud_device_name = shelly_cloud_device_name
        self._available = available

        _LOGGER.debug(self._shelly_cloud_device_name + ' >>> ' + self._shelly_cloud_entity_name + ' >>> __init__()')

    async def async_added_to_hass(self):
        # Called when an entity has their entity_id and hass object assigned, before it is written to the state
        # machine for the first time. Example uses: restore the state or subscribe to updates.
        _LOGGER.debug(self._shelly_cloud_device_name + ' >>> ' +
                      self._shelly_cloud_entity_name + ' >>> async_added_to_hass()')
        _LOGGER.debug(self._shelly_cloud_device_name + ' >>> ' +
                      self._shelly_cloud_entity_name + ' >>> entity_id: ' +
                      self.entity_id)
        async_dispatcher_connect(self.hass,
                                 SIGNAL_DELETE_ENTITY,
                                 self._delete_callback)
        async_dispatcher_connect(self.hass,
                                 SIGNAL_UPDATE_ENTITY,
                                 self._update_callback)
        return True

    async def async_will_remove_from_hass(self):
        # Called when an entity is about to be removed from Home Assistant. Example use: disconnect from the server or
        # unsubscribe from updates
        _LOGGER.debug(self._shelly_cloud_device_name + ' >>> ' +
                      self._shelly_cloud_entity_name + ' >>> async_will_remove_from_hass()')
        return True

    async def async_update(self):
        # update is done in the update function
        _LOGGER.debug(self._shelly_cloud_device_name + ' >>> ' +
                      self._shelly_cloud_entity_name + ' >>> async_update()')
        return True

    @property
    def device_id(self):
        # Return shelly_cloud device id.
        _LOGGER.debug(self._shelly_cloud_device_name + ' >>> ' +
                      self._shelly_cloud_entity_name + ' >>> device_id() >>> ' +
                      self._shelly_cloud_device_id)
        return self._shelly_cloud_device_id

    @property
    def unique_id(self):
        # Return a unique ID."
        _LOGGER.debug(self._shelly_cloud_device_name + ' >>> ' +
                      self._shelly_cloud_entity_name + ' >>> unique_id() >>> ' +
                      self.entity_id)
        return self.entity_id

    @property
    def name(self):
        # Return shelly_cloud device name.
        _LOGGER.debug(self._shelly_cloud_device_name + ' >>> ' +
                      self._shelly_cloud_entity_name + ' >>> name() >>> ' +
                      self._shelly_cloud_device_name)
        return self._shelly_cloud_device_name

    @property
    def available(self):
        # Return if the device is available.
        _LOGGER.debug(self._shelly_cloud_device_name + ' >>> ' +
                      self._shelly_cloud_entity_name + ' >>> available() >>> ' +
                      str(self._available))
        return self._available

    @callback
    def _delete_callback(self, entity_id):
        # Remove this entity.
        if entity_id == self.entity_id:
            _LOGGER.debug(self._shelly_cloud_device_name + ' >>> ' +
                          self._shelly_cloud_entity_name + ' >>> _delete_callback()')
            self.hass.async_create_task(self.async_remove())

    @callback
    def _update_callback(self):
        # Call update method.
        _LOGGER.debug(self._shelly_cloud_device_name + ' >>> ' +
                      self._shelly_cloud_entity_name + ' >>> _update_callback()')
        self.async_schedule_update_ha_state(True)
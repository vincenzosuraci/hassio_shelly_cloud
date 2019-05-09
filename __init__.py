import datetime
from datetime import timedelta
import logging
import voluptuous as vol
import requests
import hashlib
import time

from homeassistant.const import (CONF_USERNAME, CONF_PASSWORD, CONF_SCAN_INTERVAL)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

import socketio

""" Setting log """
_LOGGER = logging.getLogger('shelly_cloud_init')
_LOGGER.setLevel(logging.DEBUG)

""" This is needed to ensure shelly_cloud_iot library is always updated """
""" Ref: https://developers.home-assistant.io/docs/en/creating_integration_manifest.html"""
REQUIREMENTS = ['python-socketio[asyncio_client]']

""" This is needed, it impact on the name to be called in configurations.yaml """
""" Ref: https://developers.home-assistant.io/docs/en/creating_integration_manifest.html"""
DOMAIN = 'shelly_cloud'

SIGNAL_DELETE_ENTITY = 'shelly_cloud_delete'
SIGNAL_UPDATE_ENTITY = 'shelly_cloud_update'

HA_SWITCH = 'switch'
HA_SENSOR = 'sensor'

DEFAULT_SCAN_INTERVAL = timedelta(seconds=10)
DEFAULT_SHELLY_CLOUD_DEVICES_SCAN_INTERVAL = timedelta(minutes=15)

CONF_SHELLY_CLOUD_DEVICES_SCAN_INTERVAL = 'shelly_cloud_devices_scan_interval'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,

        vol.Optional(CONF_SCAN_INTERVAL,
                     default=DEFAULT_SCAN_INTERVAL): cv.time_period,
        vol.Optional(CONF_SHELLY_CLOUD_DEVICES_SCAN_INTERVAL,
                     default=DEFAULT_SHELLY_CLOUD_DEVICES_SCAN_INTERVAL): cv.time_period,
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
# SHELLY WEBSOCKET
# - from time-driven (polling) to event-driven strategy
#
# ----------------------------------------------------------------------------------------------------------------------

#   EXAMPLE:
#   socket = io(
#       notifications_url,
#       {   secure: true,
#           reconnection: true,
#           path: '/shelly/wss/sock'
#       });
#   console.log('******************SOCKET*********************');
#   console.log(socket);
#   // on connection - authenticate
#   socket.on('connect', function () {
#       console.log('**********SOCKET CONNECT****************');
#       console.log(socket);
#       socket.emit(    'auth',
#                       {name: name, auth: auth}
#                   );
#       online_status.set_status(true, true, true);
#       });

async def async_socketio(hass, config):

    _LOGGER.info('async_socketio()')

    params = {
        'secure': True,
        'reconnection': True,
        'path': '/shelly/wss/sock',
    }

    sio = socketio.AsyncClient(params)

    notifications_urls = hass.data[DOMAIN].get_notifications_urls()

    _LOGGER.info(notifications_urls)

    if len(notifications_urls) > 0:

        name = hass.data[DOMAIN].username
        auth = hass.data[DOMAIN].auth

        notifications_url = notifications_urls[0]

        _LOGGER.info('socketio connecting to ' + notifications_url)
        await sio.connect(notifications_url)
        _LOGGER.info('connected!')

        @sio.on('connect')
        async def on_connect():
            _LOGGER.info('I\'m connected!')
            await sio.emit('auth', {'name': name, 'auth': auth})

        @sio.on('message')
        async def on_message(data):
            _LOGGER.info('I received a message!')
            _LOGGER.info(str(data))

        @sio.on('my message')
        async def on_message(data):
            _LOGGER.info('I received a custom message!')
            _LOGGER.info(str(data))

        @sio.on('disconnect')
        async def on_disconnect():
            _LOGGER.info('I\'m disconnected!')

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

        # scan intervals
        self.update_devices_status_interval = config[DOMAIN][CONF_SCAN_INTERVAL]
        self.discover_devices_interval = config[DOMAIN][CONF_SHELLY_CLOUD_DEVICES_SCAN_INTERVAL]

        # Shelly Cloud credentials
        self.username = config[DOMAIN][CONF_USERNAME]
        self._password = config[DOMAIN][CONF_PASSWORD]

        # do login and get data (False otherwise...)
        self.auth = None
        self._user_api_url = None
        self._data = self.login()
        if self._data:
            self._user_api_url = self._data['user_api_url']
            self.auth = self._data['token']
            # start websocket
            # hass.async_create_task(async_socketio(hass, config))

        # if we have data, get device list and status
        self.devices = {}
        self.devices_status = {}
        if self._data:
            self.devices = self.get_device_list()
            if self.devices:
                self.devices_status = self.get_devices_status()

        # switch discovery
        self._discovered_switches_device_ids = []
        self.discover_switches()

        # sensor discovery
        self._discovered_sensors_device_ids = []
        self.discover_sensors()

        # starting timers
        hass.async_create_task(self.async_start_timer())

    async def async_start_timer(self):

        # This is used to update the Meross Devices status periodically
        _LOGGER.info('Shelly Cloud devices status will be updated each ' + str(self.update_devices_status_interval))
        async_track_time_interval(self._hass,
                                  self.async_update_devices,
                                  self.update_devices_status_interval)

        # This is used to discover new Meross Devices periodically
        _LOGGER.info('Shelly Cloud devices list will be updated each ' + str(self.discover_devices_interval))
        async_track_time_interval(self._hass,
                                  self.async_discover_devices,
                                  self.discover_devices_interval)

        return True

    async def async_update_devices(self, now=None):

        # monitor the duration in millis
        # registering starting timestamp in ms
        start_ms = int(round(time.time() * 1000))

        _LOGGER.debug('async_update_plugs() >>> STARTED at ' + str(now))

        self.devices_status = self.get_devices_status()

        _LOGGER.debug('async_update_plugs() <<< TERMINATED')

        # registering ending timestamp in ms
        end_ms = int(round(time.time() * 1000))
        duration_ms = end_ms - start_ms
        duration_s = int(round(duration_ms / 1000))
        duration_td = datetime.timedelta(seconds=duration_s)
        if duration_td > self.update_devices_status_interval:
            _LOGGER.warning('Updating the Shelly Cloud devices status took ' + str(duration_td))

        return True

    async def async_discover_devices(self, now=None):

        _LOGGER.debug('async_discover_plugs >>> STARTED at ' + str(now))

        # get all the registered devices
        self.devices = self.get_device_list()
        self.discover_switches()

        _LOGGER.debug('async_discover_plugs <<< FINISHED')

        return True

    def login(self):
        # login url
        url = 'https://api.shelly.cloud/auth/login'
        # get e-mail
        email = self.username
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
            _LOGGER.info('Login successful')
            return data['data']
        else:
            _LOGGER.info('Login failed')
            # print errors
            errors = data['errors']
            for error_title, error_message in errors.items():
                _LOGGER.error(error_title + ' : ' + error_message)
        return False

    def get_device_switch_status(self, device_id, channel):
        # check if device is present in the list
        if device_id in self.devices_status:
            # get device status info
            device_status_info = self.devices_status[device_id]
            if 'relays' in device_status_info:
                # check if the device channel is on
                if channel < len(device_status_info['relays']):
                    return device_status_info['relays'][channel]['ison']
                else:
                    _LOGGER.warning('get_device_switch_status() >>> channel ' +
                                    str(channel) + ' in device id ' +
                                    str(device_id) + ' not found')
            else:
                _LOGGER.warning('get_device_switch_status() >>> device id ' +
                                str(device_id) + ' has no relays')
        else:
            _LOGGER.warning('get_device_switch_status() >>> device id ' +
                            str(device_id) + ' not found')
        # otherwise, return false
        return False

    def get_device_availability(self, device_id):
        # check if device is present in the list
        if device_id in self.devices_status:
            # get device status info
            device_status_info = self.devices_status[device_id]
            # check if the device is connected to the cloud
            if device_status_info['cloud']['connected']:
                # return the enabled value
                return device_status_info['cloud']['enabled']
        else:
            _LOGGER.warning('get_device_availability() >>> device id ' +
                            str(device_id) + ' not found')
        # otherwise, return false
        return False

    def get_device_list(self):
        # device list url
        url = self._user_api_url + '/interface/device/list'
        # get response
        response = requests.post(url, headers={'Authorization': 'Bearer ' + self._data['token']})
        # get dict of POST response
        data = response.json()
        # check if everything is Ok
        if data['isok']:
            _LOGGER.info('Device list successful')
            # get_device_list was succesful!
            return data['data']['devices']
        else:
            # print errors
            _LOGGER.info('Device list failed')
            errors = data['errors']
            for error_title, error_message in errors.items():
                _LOGGER.error(error_title + ' : ' + error_message)
        return False

    def get_devices_status(self):
        # device list url
        url = self._user_api_url + '/device/all_status?_=' + str(time.time())
        # get response
        response = requests.get(url, headers={'Authorization': 'Bearer ' + self._data['token']})
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
        params = {'id': id, 'channel': channel, 'turn': turn}
        # get response
        response = requests.post(url, params, headers = {'Authorization': 'Bearer ' + self._data['token']})
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

    def get_notifications_urls(self):
        if self._data:
            return self._data['notifications_urls']

    def discover_sensors(self):
        if self.devices:
            for device_id, device_info in self.devices.items():
                if device_id not in self._discovered_sensors_device_ids:
                    self._discovered_sensors_device_ids.append(device_id)
                    self._hass.async_create_task(
                        discovery.async_load_platform(self._hass,
                                                      HA_SENSOR,
                                                      DOMAIN,
                                                      {'shelly_cloud_device_id': device_id},
                                                      self._config))

    def discover_switches(self):
        if self.devices:
            for device_id, device_info in self.devices.items():
                if device_id not in self._discovered_switches_device_ids:
                    self._discovered_switches_device_ids.append(device_id)
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
from datetime import timedelta
import logging
import voluptuous as vol
import requests
import hashlib

from homeassistant.const import (CONF_USERNAME, CONF_PASSWORD, CONF_SCAN_INTERVAL)
from homeassistant.helpers import config_validation as cv

""" Setting log """
_LOGGER = logging.getLogger('shelly_cloud_init')
_LOGGER.setLevel(logging.DEBUG)

""" This is needed to ensure meross_iot library is always updated """
""" Ref: https://developers.home-assistant.io/docs/en/creating_integration_manifest.html"""
REQUIREMENTS = []

""" This is needed, it impact on the name to be called in configurations.yaml """
""" Ref: https://developers.home-assistant.io/docs/en/creating_integration_manifest.html"""
DOMAIN = 'shelly_cloud'

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
            self._devices = self.get_device_list()
            if self._devices:
                self._devices_status = self.get_devices_status()
                _LOGGER.debug(self._devices_status)

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

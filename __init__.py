from datetime import timedelta
import logging
import voluptuous as vol
import threading

from requests.exceptions import ConnectionError

from homeassistant.core import callback
from homeassistant.const import (CONF_USERNAME, CONF_PASSWORD, CONF_SCAN_INTERVAL)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.helpers.dispatcher import (dispatcher_send, async_dispatcher_connect)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

""" Setting log """
_LOGGER = logging.getLogger('shelly_cloud_init')
_LOGGER.setLevel(logging.DEBUG)

""" This is needed to ensure meross_iot library is always updated """
""" Ref: https://developers.home-assistant.io/docs/en/creating_integration_manifest.html"""
REQUIREMENTS = ['']

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

    # TODO: get token


    _LOGGER.debug('async_setup() <<< TERMINATED')

    return True
"""Support for RFXtrx binary sensors."""
import logging

import RFXtrx as rfxtrxmod

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import (
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_DEVICE_CLASS,
    CONF_DEVICES,
)
from homeassistant.core import callback
from homeassistant.helpers import event as evt

from . import (
    CONF_AUTOMATIC_ADD,
    CONF_DATA_BITS,
    CONF_OFF_DELAY,
    SIGNAL_EVENT,
    RfxtrxEntity,
    find_possible_pt2262_device,
    get_device_id,
    get_pt2262_cmd,
    get_rfx_object,
)
from .const import (
    ATTR_EVENT,
    COMMAND_OFF_LIST,
    COMMAND_ON_LIST,
    DATA_RFXTRX_CONFIG,
    DEVICE_PACKET_TYPE_LIGHTING4,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass, config_entry, async_add_entities,
):
    """Set up platform."""
    sensors = []

    device_ids = set()
    pt2262_devices = []

    discovery_info = hass.data[DATA_RFXTRX_CONFIG]

    def supported(event):
        return isinstance(event, rfxtrxmod.ControlEvent)

    for packet_id, entity in discovery_info[CONF_DEVICES].items():
        event = get_rfx_object(packet_id)
        if event is None:
            _LOGGER.error("Invalid device: %s", packet_id)
            continue
        if not supported(event):
            continue

        device_id = get_device_id(event.device, data_bits=entity.get(CONF_DATA_BITS))
        if device_id in device_ids:
            continue
        device_ids.add(device_id)

        if event.device.packettype == DEVICE_PACKET_TYPE_LIGHTING4:
            find_possible_pt2262_device(pt2262_devices, event.device.id_string)
            pt2262_devices.append(event.device.id_string)

        device = RfxtrxBinarySensor(
            event.device,
            device_id,
            entity.get(CONF_DEVICE_CLASS),
            entity.get(CONF_OFF_DELAY),
            entity.get(CONF_DATA_BITS),
            entity.get(CONF_COMMAND_ON),
            entity.get(CONF_COMMAND_OFF),
        )
        sensors.append(device)

    async_add_entities(sensors)

    @callback
    def binary_sensor_update(event, device_id):
        """Call for control updates from the RFXtrx gateway."""
        if not supported(event):
            return

        if device_id in device_ids:
            return
        device_ids.add(device_id)

        _LOGGER.info(
            "Added binary sensor (Device ID: %s Class: %s Sub: %s Event: %s)",
            event.device.id_string.lower(),
            event.device.__class__.__name__,
            event.device.subtype,
            "".join(f"{x:02x}" for x in event.data),
        )
        sensor = RfxtrxBinarySensor(event.device, device_id, event=event)
        async_add_entities([sensor])

    # Subscribe to main RFXtrx events
    if discovery_info[CONF_AUTOMATIC_ADD]:
        hass.helpers.dispatcher.async_dispatcher_connect(
            SIGNAL_EVENT, binary_sensor_update
        )


class RfxtrxBinarySensor(RfxtrxEntity, BinarySensorEntity):
    """A representation of a RFXtrx binary sensor."""

    def __init__(
        self,
        device,
        device_id,
        device_class=None,
        off_delay=None,
        data_bits=None,
        cmd_on=None,
        cmd_off=None,
        event=None,
    ):
        """Initialize the RFXtrx sensor."""
        super().__init__(device, device_id, event=event)
        self._device_class = device_class
        self._data_bits = data_bits
        self._off_delay = off_delay
        self._state = None
        self._delay_listener = None
        self._cmd_on = cmd_on
        self._cmd_off = cmd_off

    async def async_added_to_hass(self):
        """Restore device state."""
        await super().async_added_to_hass()

        if self._event is None:
            old_state = await self.async_get_last_state()
            if old_state is not None:
                event = old_state.attributes.get(ATTR_EVENT)
                if event:
                    self._apply_event(get_rfx_object(event))

    @property
    def force_update(self) -> bool:
        """We should force updates. Repeated states have meaning."""
        return True

    @property
    def device_class(self):
        """Return the sensor class."""
        return self._device_class

    @property
    def is_on(self):
        """Return true if the sensor state is True."""
        return self._state

    def _apply_event_lighting4(self, event):
        """Apply event for a lighting 4 device."""
        if self._data_bits is not None:
            cmd = get_pt2262_cmd(event.device.id_string, self._data_bits)
            cmd = int(cmd, 16)
            if cmd == self._cmd_on:
                self._state = True
            elif cmd == self._cmd_off:
                self._state = False
        else:
            self._state = True

    def _apply_event_standard(self, event):
        if event.values["Command"] in COMMAND_ON_LIST:
            self._state = True
        elif event.values["Command"] in COMMAND_OFF_LIST:
            self._state = False

    def _apply_event(self, event):
        """Apply command from rfxtrx."""
        super()._apply_event(event)
        if event.device.packettype == DEVICE_PACKET_TYPE_LIGHTING4:
            self._apply_event_lighting4(event)
        else:
            self._apply_event_standard(event)

    @callback
    def _handle_event(self, event, device_id):
        """Check if event applies to me and update."""
        if device_id != self._device_id:
            return

        _LOGGER.debug(
            "Binary sensor update (Device ID: %s Class: %s Sub: %s)",
            event.device.id_string,
            event.device.__class__.__name__,
            event.device.subtype,
        )

        self._apply_event(event)

        self.async_write_ha_state()

        if self.is_on and self._off_delay is not None and self._delay_listener is None:

            @callback
            def off_delay_listener(now):
                """Switch device off after a delay."""
                self._delay_listener = None
                self._state = False
                self.async_write_ha_state()

            self._delay_listener = evt.async_call_later(
                self.hass, self._off_delay.total_seconds(), off_delay_listener
            )

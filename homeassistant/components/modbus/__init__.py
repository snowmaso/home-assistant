"""Support for Modbus."""
import asyncio
import logging

from async_timeout import timeout
from pymodbus.client.asynchronous import schedulers
from pymodbus.client.asynchronous.serial import AsyncModbusSerialClient as ClientSerial
from pymodbus.client.asynchronous.tcp import AsyncModbusTCPClient as ClientTCP
from pymodbus.client.asynchronous.udp import AsyncModbusUDPClient as ClientUDP
from pymodbus.exceptions import ModbusException
from pymodbus.pdu import ExceptionResponse
from pymodbus.transaction import ModbusRtuFramer
import voluptuous as vol

from homeassistant.const import (
    ATTR_STATE,
    CONF_DELAY,
    CONF_HOST,
    CONF_METHOD,
    CONF_NAME,
    CONF_PORT,
    CONF_TIMEOUT,
    CONF_TYPE,
    EVENT_HOMEASSISTANT_STOP,
)
import homeassistant.helpers.config_validation as cv

from .const import (
    ATTR_ADDRESS,
    ATTR_HUB,
    ATTR_UNIT,
    ATTR_VALUE,
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_PARITY,
    CONF_STOPBITS,
    DEFAULT_HUB,
    MODBUS_DOMAIN as DOMAIN,
    SERVICE_WRITE_COIL,
    SERVICE_WRITE_REGISTER,
)

_LOGGER = logging.getLogger(__name__)

BASE_SCHEMA = vol.Schema({vol.Optional(CONF_NAME, default=DEFAULT_HUB): cv.string})

SERIAL_SCHEMA = BASE_SCHEMA.extend(
    {
        vol.Required(CONF_BAUDRATE): cv.positive_int,
        vol.Required(CONF_BYTESIZE): vol.Any(5, 6, 7, 8),
        vol.Required(CONF_METHOD): vol.Any("rtu", "ascii"),
        vol.Required(CONF_PORT): cv.string,
        vol.Required(CONF_PARITY): vol.Any("E", "O", "N"),
        vol.Required(CONF_STOPBITS): vol.Any(1, 2),
        vol.Required(CONF_TYPE): "serial",
        vol.Optional(CONF_TIMEOUT, default=3): cv.socket_timeout,
    }
)

ETHERNET_SCHEMA = BASE_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT): cv.port,
        vol.Required(CONF_TYPE): vol.Any("tcp", "udp", "rtuovertcp"),
        vol.Optional(CONF_TIMEOUT, default=3): cv.socket_timeout,
        vol.Optional(CONF_DELAY, default=0): cv.positive_int,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [vol.Any(SERIAL_SCHEMA, ETHERNET_SCHEMA)])},
    extra=vol.ALLOW_EXTRA,
)

SERVICE_WRITE_REGISTER_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_HUB, default=DEFAULT_HUB): cv.string,
        vol.Required(ATTR_UNIT): cv.positive_int,
        vol.Required(ATTR_ADDRESS): cv.positive_int,
        vol.Required(ATTR_VALUE): vol.Any(
            cv.positive_int, vol.All(cv.ensure_list, [cv.positive_int])
        ),
    }
)

SERVICE_WRITE_COIL_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_HUB, default=DEFAULT_HUB): cv.string,
        vol.Required(ATTR_UNIT): cv.positive_int,
        vol.Required(ATTR_ADDRESS): cv.positive_int,
        vol.Required(ATTR_STATE): cv.boolean,
    }
)


async def async_setup(hass, config):
    """Set up Modbus component."""
    hass.data[DOMAIN] = hub_collect = {}

    for client_config in config[DOMAIN]:
        hub_collect[client_config[CONF_NAME]] = ModbusHub(client_config, hass.loop)

    def stop_modbus(event):
        """Stop Modbus service."""
        for client in hub_collect.values():
            del client

    def start_modbus():
        """Start Modbus service."""
        for client in hub_collect.values():
            client.setup()

        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_modbus)

    async def write_register(service):
        """Write Modbus registers."""
        unit = int(float(service.data[ATTR_UNIT]))
        address = int(float(service.data[ATTR_ADDRESS]))
        value = service.data[ATTR_VALUE]
        client_name = service.data[ATTR_HUB]
        if isinstance(value, list):
            await hub_collect[client_name].write_registers(
                unit, address, [int(float(i)) for i in value]
            )
        else:
            await hub_collect[client_name].write_register(
                unit, address, int(float(value))
            )

    async def write_coil(service):
        """Write Modbus coil."""
        unit = service.data[ATTR_UNIT]
        address = service.data[ATTR_ADDRESS]
        state = service.data[ATTR_STATE]
        client_name = service.data[ATTR_HUB]
        await hub_collect[client_name].write_coil(unit, address, state)

    # do not wait for EVENT_HOMEASSISTANT_START, activate pymodbus now
    await hass.async_add_executor_job(start_modbus)

    # Register services for modbus
    hass.services.async_register(
        DOMAIN,
        SERVICE_WRITE_REGISTER,
        write_register,
        schema=SERVICE_WRITE_REGISTER_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_WRITE_COIL, write_coil, schema=SERVICE_WRITE_COIL_SCHEMA,
    )
    return True


class ModbusHub:
    """Thread safe wrapper class for pymodbus."""

    def __init__(self, client_config, main_loop):
        """Initialize the Modbus hub."""

        # generic configuration
        self._loop = main_loop
        self._client = None
        self._lock = asyncio.Lock()
        self._config_name = client_config[CONF_NAME]
        self._config_type = client_config[CONF_TYPE]
        self._config_port = client_config[CONF_PORT]
        self._config_timeout = client_config[CONF_TIMEOUT]
        self._config_delay = 0

        if self._config_type == "serial":
            # serial configuration
            self._config_method = client_config[CONF_METHOD]
            self._config_baudrate = client_config[CONF_BAUDRATE]
            self._config_stopbits = client_config[CONF_STOPBITS]
            self._config_bytesize = client_config[CONF_BYTESIZE]
            self._config_parity = client_config[CONF_PARITY]
        else:
            # network configuration
            self._config_host = client_config[CONF_HOST]
            self._config_delay = client_config[CONF_DELAY]

    @property
    def name(self):
        """Return the name of this hub."""
        return self._config_name

    async def _connect_delay(self):
        if self._config_delay > 0:
            await asyncio.sleep(self._config_delay)
            self._config_delay = 0

    def setup(self):
        """Set up pymodbus client."""
        # pylint: disable = E0633
        # Client* do deliver loop, client as result but
        # pylint does not accept that fact

        if self._config_type == "serial":
            _, self._client = ClientSerial(
                schedulers.ASYNC_IO,
                method=self._config_method,
                port=self._config_port,
                baudrate=self._config_baudrate,
                stopbits=self._config_stopbits,
                bytesize=self._config_bytesize,
                parity=self._config_parity,
                loop=self._loop,
            )
        elif self._config_type == "rtuovertcp":
            _, self._client = ClientTCP(
                schedulers.ASYNC_IO,
                host=self._config_host,
                port=self._config_port,
                framer=ModbusRtuFramer,
                timeout=self._config_timeout,
                loop=self._loop,
            )
        elif self._config_type == "tcp":
            _, self._client = ClientTCP(
                schedulers.ASYNC_IO,
                host=self._config_host,
                port=self._config_port,
                timeout=self._config_timeout,
                loop=self._loop,
            )
        elif self._config_type == "udp":
            _, self._client = ClientUDP(
                schedulers.ASYNC_IO,
                host=self._config_host,
                port=self._config_port,
                timeout=self._config_timeout,
                loop=self._loop,
            )
        else:
            assert False

    async def _read(self, unit, address, count, func):
        """Read generic with error handling."""
        await self._connect_delay()
        async with self._lock:
            kwargs = {"unit": unit} if unit else {}
            try:
                async with timeout(self._config_timeout):
                    result = await func(address, count, **kwargs)
            except asyncio.TimeoutError:
                result = None

            if isinstance(result, (ModbusException, ExceptionResponse)):
                _LOGGER.error("Hub %s Exception (%s)", self._config_name, result)
            return result

    async def _write(self, unit, address, value, func):
        """Read generic with error handling."""
        await self._connect_delay()
        async with self._lock:
            kwargs = {"unit": unit} if unit else {}
            try:
                async with timeout(self._config_timeout):
                    func(address, value, **kwargs)
            except asyncio.TimeoutError:
                return

    async def read_coils(self, unit, address, count):
        """Read coils."""
        if self._client.protocol is None:
            return None
        return await self._read(unit, address, count, self._client.protocol.read_coils)

    async def read_discrete_inputs(self, unit, address, count):
        """Read discrete inputs."""
        if self._client.protocol is None:
            return None
        return await self._read(
            unit, address, count, self._client.protocol.read_discrete_inputs
        )

    async def read_input_registers(self, unit, address, count):
        """Read input registers."""
        if self._client.protocol is None:
            return None
        return await self._read(
            unit, address, count, self._client.protocol.read_input_registers
        )

    async def read_holding_registers(self, unit, address, count):
        """Read holding registers."""
        if self._client.protocol is None:
            return None
        return await self._read(
            unit, address, count, self._client.protocol.read_holding_registers
        )

    async def write_coil(self, unit, address, value):
        """Write coil."""
        if self._client.protocol is None:
            return None
        return await self._write(unit, address, value, self._client.protocol.write_coil)

    async def write_register(self, unit, address, value):
        """Write register."""
        if self._client.protocol is None:
            return None
        return await self._write(
            unit, address, value, self._client.protocol.write_register
        )

    async def write_registers(self, unit, address, values):
        """Write registers."""
        if self._client.protocol is None:
            return None
        return await self._write(
            unit, address, values, self._client.protocol.write_registers
        )

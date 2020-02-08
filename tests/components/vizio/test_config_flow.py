"""Tests for Vizio config flow."""
import logging

from asynctest import patch
import pytest
import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.media_player import DEVICE_CLASS_SPEAKER, DEVICE_CLASS_TV
from homeassistant.components.vizio.const import (
    CONF_VOLUME_STEP,
    DEFAULT_NAME,
    DEFAULT_VOLUME_STEP,
    DOMAIN,
    VIZIO_SCHEMA,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_DEVICE_CLASS,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_TYPE,
)
from homeassistant.helpers.typing import HomeAssistantType

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)

NAME = "Vizio"
NAME2 = "Vizio2"
HOST = "192.168.1.1:9000"
HOST2 = "192.168.1.2:9000"
ACCESS_TOKEN = "deadbeef"
VOLUME_STEP = 2
UNIQUE_ID = "testid"

MOCK_USER_VALID_TV_CONFIG = {
    CONF_NAME: NAME,
    CONF_HOST: HOST,
    CONF_DEVICE_CLASS: DEVICE_CLASS_TV,
    CONF_ACCESS_TOKEN: ACCESS_TOKEN,
}

MOCK_IMPORT_VALID_TV_CONFIG = {
    CONF_NAME: NAME,
    CONF_HOST: HOST,
    CONF_DEVICE_CLASS: DEVICE_CLASS_TV,
    CONF_ACCESS_TOKEN: ACCESS_TOKEN,
    CONF_VOLUME_STEP: VOLUME_STEP,
}

MOCK_INVALID_TV_CONFIG = {
    CONF_NAME: NAME,
    CONF_HOST: HOST,
    CONF_DEVICE_CLASS: DEVICE_CLASS_TV,
}

MOCK_SPEAKER_CONFIG = {
    CONF_NAME: NAME,
    CONF_HOST: HOST,
    CONF_DEVICE_CLASS: DEVICE_CLASS_SPEAKER,
}

VIZIO_ZEROCONF_SERVICE_TYPE = "_viziocast._tcp.local."
ZEROCONF_NAME = f"{NAME}.{VIZIO_ZEROCONF_SERVICE_TYPE}"
ZEROCONF_HOST = HOST.split(":")[0]
ZEROCONF_PORT = HOST.split(":")[1]

MOCK_ZEROCONF_ENTRY = {
    CONF_TYPE: VIZIO_ZEROCONF_SERVICE_TYPE,
    CONF_NAME: ZEROCONF_NAME,
    CONF_HOST: ZEROCONF_HOST,
    CONF_PORT: ZEROCONF_PORT,
    "properties": {"name": "SB4031-D5"},
}


@pytest.fixture(name="vizio_connect")
def vizio_connect_fixture():
    """Mock valid vizio device and entry setup."""
    with patch(
        "homeassistant.components.vizio.config_flow.VizioAsync.validate_ha_config",
        return_value=True,
    ), patch(
        "homeassistant.components.vizio.config_flow.VizioAsync.get_unique_id",
        return_value=UNIQUE_ID,
    ):
        yield


@pytest.fixture(name="vizio_bypass_setup")
def vizio_bypass_setup_fixture():
    """Mock component setup."""
    with patch("homeassistant.components.vizio.async_setup_entry", return_value=True):
        yield


@pytest.fixture(name="vizio_bypass_update")
def vizio_bypass_update_fixture():
    """Mock component update."""
    with patch(
        "homeassistant.components.vizio.media_player.VizioAsync.can_connect",
        return_value=True,
    ), patch("homeassistant.components.vizio.media_player.VizioDevice.async_update"):
        yield


@pytest.fixture(name="vizio_guess_device_type")
def vizio_guess_device_type_fixture():
    """Mock vizio async_guess_device_type function."""
    with patch(
        "homeassistant.components.vizio.config_flow.async_guess_device_type",
        return_value="speaker",
    ):
        yield


@pytest.fixture(name="vizio_cant_connect")
def vizio_cant_connect_fixture():
    """Mock vizio device cant connect."""
    with patch(
        "homeassistant.components.vizio.config_flow.VizioAsync.validate_ha_config",
        return_value=False,
    ):
        yield


async def test_user_flow_minimum_fields(
    hass: HomeAssistantType,
    vizio_connect: pytest.fixture,
    vizio_bypass_setup: pytest.fixture,
) -> None:
    """Test user config flow with minimum fields."""
    # test form shows
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_NAME: NAME,
            CONF_HOST: HOST,
            CONF_DEVICE_CLASS: DEVICE_CLASS_SPEAKER,
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"][CONF_NAME] == NAME
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_DEVICE_CLASS] == DEVICE_CLASS_SPEAKER


async def test_user_flow_all_fields(
    hass: HomeAssistantType,
    vizio_connect: pytest.fixture,
    vizio_bypass_setup: pytest.fixture,
) -> None:
    """Test user config flow with all fields."""
    # test form shows
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_NAME: NAME,
            CONF_HOST: HOST,
            CONF_DEVICE_CLASS: DEVICE_CLASS_TV,
            CONF_ACCESS_TOKEN: ACCESS_TOKEN,
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"][CONF_NAME] == NAME
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_DEVICE_CLASS] == DEVICE_CLASS_TV
    assert result["data"][CONF_ACCESS_TOKEN] == ACCESS_TOKEN


async def test_options_flow(hass: HomeAssistantType) -> None:
    """Test options config flow."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_SPEAKER_CONFIG)
    entry.add_to_hass(hass)

    assert not entry.options

    result = await hass.config_entries.options.async_init(entry.entry_id, data=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_VOLUME_STEP: VOLUME_STEP}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == ""
    assert result["data"][CONF_VOLUME_STEP] == VOLUME_STEP


async def test_user_host_already_configured(
    hass: HomeAssistantType,
    vizio_connect: pytest.fixture,
    vizio_bypass_setup: pytest.fixture,
) -> None:
    """Test host is already configured during user setup."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_SPEAKER_CONFIG, options={CONF_VOLUME_STEP: VOLUME_STEP}
    )
    entry.add_to_hass(hass)
    fail_entry = MOCK_SPEAKER_CONFIG.copy()
    fail_entry[CONF_NAME] = "newtestname"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=fail_entry
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_HOST: "host_exists"}


async def test_user_host_already_configured_no_port(
    hass: HomeAssistantType,
    vizio_connect: pytest.fixture,
    vizio_bypass_setup: pytest.fixture,
) -> None:
    """Test host is already configured during user setup when existing entry has no port."""
    # Mock entry without port so we can test that the same entry WITH a port will fail
    no_port_entry = MOCK_SPEAKER_CONFIG.copy()
    no_port_entry[CONF_HOST] = no_port_entry[CONF_HOST].split(":")[0]
    entry = MockConfigEntry(
        domain=DOMAIN, data=no_port_entry, options={CONF_VOLUME_STEP: VOLUME_STEP}
    )
    entry.add_to_hass(hass)
    fail_entry = MOCK_SPEAKER_CONFIG.copy()
    fail_entry[CONF_NAME] = "newtestname"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=fail_entry
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_HOST: "host_exists"}


async def test_user_name_already_configured(
    hass: HomeAssistantType,
    vizio_connect: pytest.fixture,
    vizio_bypass_setup: pytest.fixture,
) -> None:
    """Test name is already configured during user setup."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_SPEAKER_CONFIG, options={CONF_VOLUME_STEP: VOLUME_STEP}
    )
    entry.add_to_hass(hass)

    fail_entry = MOCK_SPEAKER_CONFIG.copy()
    fail_entry[CONF_HOST] = "0.0.0.0"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=fail_entry
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_NAME: "name_exists"}


async def test_user_esn_already_exists(
    hass: HomeAssistantType,
    vizio_connect: pytest.fixture,
    vizio_bypass_setup: pytest.fixture,
) -> None:
    """Test ESN is already configured with different host and name during user setup."""
    # Set up new entry
    MockConfigEntry(
        domain=DOMAIN, data=MOCK_SPEAKER_CONFIG, unique_id=UNIQUE_ID
    ).add_to_hass(hass)

    # Set up new entry with same unique_id but different host and name
    fail_entry = MOCK_SPEAKER_CONFIG.copy()
    fail_entry[CONF_HOST] = HOST2
    fail_entry[CONF_NAME] = NAME2

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=fail_entry
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_setup_with_diff_host_and_name"


async def test_user_error_on_could_not_connect(
    hass: HomeAssistantType, vizio_cant_connect: pytest.fixture
) -> None:
    """Test with could_not_connect during user_setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=MOCK_USER_VALID_TV_CONFIG
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "cant_connect"}


async def test_user_error_on_tv_needs_token(
    hass: HomeAssistantType,
    vizio_connect: pytest.fixture,
    vizio_bypass_setup: pytest.fixture,
) -> None:
    """Test when config fails custom validation for non null access token when device_class = tv during user setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=MOCK_INVALID_TV_CONFIG
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "tv_needs_token"}


async def test_import_flow_minimum_fields(
    hass: HomeAssistantType,
    vizio_connect: pytest.fixture,
    vizio_bypass_setup: pytest.fixture,
) -> None:
    """Test import config flow with minimum fields."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=vol.Schema(VIZIO_SCHEMA)(
            {CONF_HOST: HOST, CONF_DEVICE_CLASS: DEVICE_CLASS_SPEAKER}
        ),
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"][CONF_NAME] == DEFAULT_NAME
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_DEVICE_CLASS] == DEVICE_CLASS_SPEAKER
    assert result["data"][CONF_VOLUME_STEP] == DEFAULT_VOLUME_STEP


async def test_import_flow_all_fields(
    hass: HomeAssistantType,
    vizio_connect: pytest.fixture,
    vizio_bypass_setup: pytest.fixture,
) -> None:
    """Test import config flow with all fields."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=vol.Schema(VIZIO_SCHEMA)(MOCK_IMPORT_VALID_TV_CONFIG),
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"][CONF_NAME] == NAME
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_DEVICE_CLASS] == DEVICE_CLASS_TV
    assert result["data"][CONF_ACCESS_TOKEN] == ACCESS_TOKEN
    assert result["data"][CONF_VOLUME_STEP] == VOLUME_STEP


async def test_import_entity_already_configured(
    hass: HomeAssistantType,
    vizio_connect: pytest.fixture,
    vizio_bypass_setup: pytest.fixture,
) -> None:
    """Test entity is already configured during import setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=vol.Schema(VIZIO_SCHEMA)(MOCK_SPEAKER_CONFIG),
        options={CONF_VOLUME_STEP: VOLUME_STEP},
    )
    entry.add_to_hass(hass)
    fail_entry = vol.Schema(VIZIO_SCHEMA)(MOCK_SPEAKER_CONFIG.copy())

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=fail_entry
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_setup"


async def test_import_flow_update_options(
    hass: HomeAssistantType,
    vizio_connect: pytest.fixture,
    vizio_bypass_update: pytest.fixture,
) -> None:
    """Test import config flow with updated options."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=vol.Schema(VIZIO_SCHEMA)(MOCK_IMPORT_VALID_TV_CONFIG),
    )
    await hass.async_block_till_done()

    assert result["result"].options == {CONF_VOLUME_STEP: VOLUME_STEP}
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    entry_id = result["result"].entry_id

    updated_config = MOCK_IMPORT_VALID_TV_CONFIG.copy()
    updated_config[CONF_VOLUME_STEP] = VOLUME_STEP + 1
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=vol.Schema(VIZIO_SCHEMA)(updated_config),
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "updated_entry"
    assert (
        hass.config_entries.async_get_entry(entry_id).options[CONF_VOLUME_STEP]
        == VOLUME_STEP + 1
    )


async def test_import_flow_update_name(
    hass: HomeAssistantType,
    vizio_connect: pytest.fixture,
    vizio_bypass_update: pytest.fixture,
) -> None:
    """Test import config flow with updated name."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=vol.Schema(VIZIO_SCHEMA)(MOCK_IMPORT_VALID_TV_CONFIG),
    )
    await hass.async_block_till_done()

    assert result["result"].data[CONF_NAME] == NAME
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    entry_id = result["result"].entry_id

    updated_config = MOCK_IMPORT_VALID_TV_CONFIG.copy()
    updated_config[CONF_NAME] = NAME2
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=vol.Schema(VIZIO_SCHEMA)(updated_config),
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "updated_entry"
    assert hass.config_entries.async_get_entry(entry_id).data[CONF_NAME] == NAME2


async def test_zeroconf_flow(
    hass: HomeAssistantType,
    vizio_connect: pytest.fixture,
    vizio_bypass_setup: pytest.fixture,
    vizio_guess_device_type: pytest.fixture,
) -> None:
    """Test zeroconf config flow."""
    discovery_info = MOCK_ZEROCONF_ENTRY.copy()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=discovery_info
    )

    # Form should always show even if all required properties are discovered
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    # Apply discovery updates to entry to mimick when user hits submit without changing
    # defaults which were set from discovery parameters
    user_input = result["data_schema"](discovery_info)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_NAME] == NAME
    assert result["data"][CONF_DEVICE_CLASS] == DEVICE_CLASS_SPEAKER


async def test_zeroconf_flow_already_configured(
    hass: HomeAssistantType,
    vizio_connect: pytest.fixture,
    vizio_bypass_setup: pytest.fixture,
) -> None:
    """Test entity is already configured during zeroconf setup."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_SPEAKER_CONFIG, options={CONF_VOLUME_STEP: VOLUME_STEP}
    )
    entry.add_to_hass(hass)

    # Try rediscovering same device
    discovery_info = MOCK_ZEROCONF_ENTRY.copy()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=discovery_info
    )

    # Flow should abort because device is already setup
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_setup"

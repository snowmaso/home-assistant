"""Tests for Plex config flow."""
from unittest.mock import MagicMock, Mock, patch, PropertyMock

import asynctest
import plexapi.exceptions
import requests.exceptions

from homeassistant.components.plex import config_flow
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN, CONF_URL
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

from .mock_classes import MOCK_HOST_1, MOCK_PORT_1, MockAvailableServer, MockConnections

MOCK_NAME_1 = "Plex Server 1"
MOCK_ID_1 = "unique_id_123"
MOCK_NAME_2 = "Plex Server 2"
MOCK_ID_2 = "unique_id_456"
MOCK_TOKEN = "secret_token"
MOCK_FILE_CONTENTS = {
    f"{MOCK_HOST_1}:{MOCK_PORT_1}": {"ssl": False, "token": MOCK_TOKEN, "verify": True}
}
MOCK_SERVER_1 = MockAvailableServer(MOCK_NAME_1, MOCK_ID_1)
MOCK_SERVER_2 = MockAvailableServer(MOCK_NAME_2, MOCK_ID_2)

DEFAULT_OPTIONS = {
    config_flow.MP_DOMAIN: {
        config_flow.CONF_USE_EPISODE_ART: False,
        config_flow.CONF_SHOW_ALL_CONTROLS: False,
    }
}


def init_config_flow(hass):
    """Init a configuration flow."""
    flow = config_flow.PlexFlowHandler()
    flow.hass = hass
    return flow


async def test_bad_credentials(hass):
    """Test when provided credentials are rejected."""
    mock_connections = MockConnections()
    mm_plex_account = MagicMock()
    mm_plex_account.resources = Mock(return_value=[MOCK_SERVER_1])
    mm_plex_account.resource = Mock(return_value=mock_connections)

    with patch("plexapi.myplex.MyPlexAccount", return_value=mm_plex_account), patch(
        "plexapi.server.PlexServer", side_effect=plexapi.exceptions.Unauthorized
    ), asynctest.patch("plexauth.PlexAuth.initiate_auth"), asynctest.patch(
        "plexauth.PlexAuth.token", return_value="BAD TOKEN"
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN, context={"source": "user"}
        )
        assert result["type"] == "form"
        assert result["step_id"] == "start_website_auth"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "external"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "external_done"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])

        assert result["type"] == "form"
        assert result["step_id"] == "start_website_auth"
        assert result["errors"]["base"] == "faulty_credentials"


async def test_import_file_from_discovery(hass):
    """Test importing a legacy file during discovery."""

    file_host_and_port, file_config = list(MOCK_FILE_CONTENTS.items())[0]
    used_url = f"http://{file_host_and_port}"

    with patch("plexapi.server.PlexServer") as mock_plex_server, patch(
        "homeassistant.components.plex.config_flow.load_json",
        return_value=MOCK_FILE_CONTENTS,
    ):
        type(mock_plex_server.return_value).machineIdentifier = PropertyMock(
            return_value=MOCK_ID_1
        )
        type(mock_plex_server.return_value).friendlyName = PropertyMock(
            return_value=MOCK_NAME_1
        )
        type(  # pylint: disable=protected-access
            mock_plex_server.return_value
        )._baseurl = PropertyMock(return_value=used_url)

        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": "discovery"},
            data={CONF_HOST: MOCK_HOST_1, CONF_PORT: MOCK_PORT_1},
        )
        assert result["type"] == "create_entry"
        assert result["title"] == MOCK_NAME_1
        assert result["data"][config_flow.CONF_SERVER] == MOCK_NAME_1
        assert result["data"][config_flow.CONF_SERVER_IDENTIFIER] == MOCK_ID_1
        assert result["data"][config_flow.PLEX_SERVER_CONFIG][CONF_URL] == used_url
        assert (
            result["data"][config_flow.PLEX_SERVER_CONFIG][CONF_TOKEN]
            == file_config[CONF_TOKEN]
        )


async def test_discovery(hass):
    """Test starting a flow from discovery."""

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": "discovery"},
        data={CONF_HOST: MOCK_HOST_1, CONF_PORT: MOCK_PORT_1},
    )
    assert result["type"] == "abort"
    assert result["reason"] == "discovery_no_file"


async def test_discovery_while_in_progress(hass):
    """Test starting a flow from discovery."""

    await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": "discovery"},
        data={CONF_HOST: MOCK_HOST_1, CONF_PORT: MOCK_PORT_1},
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_import_success(hass):
    """Test a successful configuration import."""

    mock_connections = MockConnections(ssl=True)

    mm_plex_account = MagicMock()
    mm_plex_account.resources = Mock(return_value=[MOCK_SERVER_1])
    mm_plex_account.resource = Mock(return_value=mock_connections)

    with patch("plexapi.server.PlexServer") as mock_plex_server:
        type(mock_plex_server.return_value).machineIdentifier = PropertyMock(
            return_value=MOCK_SERVER_1.clientIdentifier
        )
        type(mock_plex_server.return_value).friendlyName = PropertyMock(
            return_value=MOCK_SERVER_1.name
        )
        type(  # pylint: disable=protected-access
            mock_plex_server.return_value
        )._baseurl = PropertyMock(return_value=mock_connections.connections[0].httpuri)

        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": "import"},
            data={
                CONF_TOKEN: MOCK_TOKEN,
                CONF_URL: f"https://{MOCK_HOST_1}:{MOCK_PORT_1}",
            },
        )

    assert result["type"] == "create_entry"
    assert result["title"] == MOCK_SERVER_1.name
    assert result["data"][config_flow.CONF_SERVER] == MOCK_SERVER_1.name
    assert (
        result["data"][config_flow.CONF_SERVER_IDENTIFIER]
        == MOCK_SERVER_1.clientIdentifier
    )
    assert (
        result["data"][config_flow.PLEX_SERVER_CONFIG][CONF_URL]
        == mock_connections.connections[0].httpuri
    )
    assert result["data"][config_flow.PLEX_SERVER_CONFIG][CONF_TOKEN] == MOCK_TOKEN


async def test_import_bad_hostname(hass):
    """Test when an invalid address is provided."""

    with patch(
        "plexapi.server.PlexServer", side_effect=requests.exceptions.ConnectionError
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": "import"},
            data={
                CONF_TOKEN: MOCK_TOKEN,
                CONF_URL: f"http://{MOCK_HOST_1}:{MOCK_PORT_1}",
            },
        )
        assert result["type"] == "form"
        assert result["step_id"] == "start_website_auth"
        assert result["errors"]["base"] == "not_found"


async def test_unknown_exception(hass):
    """Test when an unknown exception is encountered."""

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "start_website_auth"

    mock_connections = MockConnections()
    mm_plex_account = MagicMock()
    mm_plex_account.resources = Mock(return_value=[MOCK_SERVER_1])
    mm_plex_account.resource = Mock(return_value=mock_connections)

    with patch("plexapi.myplex.MyPlexAccount", return_value=mm_plex_account), patch(
        "plexapi.server.PlexServer", side_effect=Exception
    ), asynctest.patch("plexauth.PlexAuth.initiate_auth"), asynctest.patch(
        "plexauth.PlexAuth.token", return_value="MOCK_TOKEN"
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "external"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "external_done"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "abort"
        assert result["reason"] == "unknown"


async def test_no_servers_found(hass):
    """Test when no servers are on an account."""

    await async_setup_component(hass, "http", {"http": {}})

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "start_website_auth"

    mm_plex_account = MagicMock()
    mm_plex_account.resources = Mock(return_value=[])

    with patch(
        "plexapi.myplex.MyPlexAccount", return_value=mm_plex_account
    ), asynctest.patch("plexauth.PlexAuth.initiate_auth"), asynctest.patch(
        "plexauth.PlexAuth.token", return_value=MOCK_TOKEN
    ):

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "external"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "external_done"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "form"
        assert result["step_id"] == "start_website_auth"
        assert result["errors"]["base"] == "no_servers"


async def test_single_available_server(hass):
    """Test creating an entry with one server available."""

    await async_setup_component(hass, "http", {"http": {}})

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "start_website_auth"

    mock_connections = MockConnections()

    mm_plex_account = MagicMock()
    mm_plex_account.resources = Mock(return_value=[MOCK_SERVER_1])
    mm_plex_account.resource = Mock(return_value=mock_connections)

    with patch("plexapi.myplex.MyPlexAccount", return_value=mm_plex_account), patch(
        "plexapi.server.PlexServer"
    ) as mock_plex_server, asynctest.patch(
        "plexauth.PlexAuth.initiate_auth"
    ), asynctest.patch(
        "plexauth.PlexAuth.token", return_value=MOCK_TOKEN
    ):
        type(mock_plex_server.return_value).machineIdentifier = PropertyMock(
            return_value=MOCK_SERVER_1.clientIdentifier
        )
        type(mock_plex_server.return_value).friendlyName = PropertyMock(
            return_value=MOCK_SERVER_1.name
        )
        type(  # pylint: disable=protected-access
            mock_plex_server.return_value
        )._baseurl = PropertyMock(return_value=mock_connections.connections[0].httpuri)

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "external"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "external_done"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "create_entry"
        assert result["title"] == MOCK_SERVER_1.name
        assert result["data"][config_flow.CONF_SERVER] == MOCK_SERVER_1.name
        assert (
            result["data"][config_flow.CONF_SERVER_IDENTIFIER]
            == MOCK_SERVER_1.clientIdentifier
        )
        assert (
            result["data"][config_flow.PLEX_SERVER_CONFIG][CONF_URL]
            == mock_connections.connections[0].httpuri
        )
        assert result["data"][config_flow.PLEX_SERVER_CONFIG][CONF_TOKEN] == MOCK_TOKEN


async def test_multiple_servers_with_selection(hass):
    """Test creating an entry with multiple servers available."""

    await async_setup_component(hass, "http", {"http": {}})

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "start_website_auth"

    mock_connections = MockConnections()
    mm_plex_account = MagicMock()
    mm_plex_account.resources = Mock(return_value=[MOCK_SERVER_1, MOCK_SERVER_2])
    mm_plex_account.resource = Mock(return_value=mock_connections)

    with patch("plexapi.myplex.MyPlexAccount", return_value=mm_plex_account), patch(
        "plexapi.server.PlexServer"
    ) as mock_plex_server, asynctest.patch(
        "plexauth.PlexAuth.initiate_auth"
    ), asynctest.patch(
        "plexauth.PlexAuth.token", return_value=MOCK_TOKEN
    ):
        type(mock_plex_server.return_value).machineIdentifier = PropertyMock(
            return_value=MOCK_SERVER_1.clientIdentifier
        )
        type(mock_plex_server.return_value).friendlyName = PropertyMock(
            return_value=MOCK_SERVER_1.name
        )
        type(  # pylint: disable=protected-access
            mock_plex_server.return_value
        )._baseurl = PropertyMock(return_value=mock_connections.connections[0].httpuri)

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "external"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "external_done"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "form"
        assert result["step_id"] == "select_server"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={config_flow.CONF_SERVER: MOCK_SERVER_1.name}
        )
        assert result["type"] == "create_entry"
        assert result["title"] == MOCK_SERVER_1.name
        assert result["data"][config_flow.CONF_SERVER] == MOCK_SERVER_1.name
        assert (
            result["data"][config_flow.CONF_SERVER_IDENTIFIER]
            == MOCK_SERVER_1.clientIdentifier
        )
        assert (
            result["data"][config_flow.PLEX_SERVER_CONFIG][CONF_URL]
            == mock_connections.connections[0].httpuri
        )
        assert result["data"][config_flow.PLEX_SERVER_CONFIG][CONF_TOKEN] == MOCK_TOKEN


async def test_adding_last_unconfigured_server(hass):
    """Test automatically adding last unconfigured server when multiple servers on account."""

    await async_setup_component(hass, "http", {"http": {}})

    MockConfigEntry(
        domain=config_flow.DOMAIN,
        data={
            config_flow.CONF_SERVER_IDENTIFIER: MOCK_ID_2,
            config_flow.CONF_SERVER: MOCK_NAME_2,
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "start_website_auth"

    mock_connections = MockConnections()
    mm_plex_account = MagicMock()
    mm_plex_account.resources = Mock(return_value=[MOCK_SERVER_1, MOCK_SERVER_2])
    mm_plex_account.resource = Mock(return_value=mock_connections)

    with patch("plexapi.myplex.MyPlexAccount", return_value=mm_plex_account), patch(
        "plexapi.server.PlexServer"
    ) as mock_plex_server, asynctest.patch(
        "plexauth.PlexAuth.initiate_auth"
    ), asynctest.patch(
        "plexauth.PlexAuth.token", return_value=MOCK_TOKEN
    ):
        type(mock_plex_server.return_value).machineIdentifier = PropertyMock(
            return_value=MOCK_SERVER_1.clientIdentifier
        )
        type(mock_plex_server.return_value).friendlyName = PropertyMock(
            return_value=MOCK_SERVER_1.name
        )
        type(  # pylint: disable=protected-access
            mock_plex_server.return_value
        )._baseurl = PropertyMock(return_value=mock_connections.connections[0].httpuri)

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "external"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "external_done"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "create_entry"
        assert result["title"] == MOCK_SERVER_1.name
        assert result["data"][config_flow.CONF_SERVER] == MOCK_SERVER_1.name
        assert (
            result["data"][config_flow.CONF_SERVER_IDENTIFIER]
            == MOCK_SERVER_1.clientIdentifier
        )
        assert (
            result["data"][config_flow.PLEX_SERVER_CONFIG][CONF_URL]
            == mock_connections.connections[0].httpuri
        )
        assert result["data"][config_flow.PLEX_SERVER_CONFIG][CONF_TOKEN] == MOCK_TOKEN


async def test_already_configured(hass):
    """Test a duplicated successful flow."""

    flow = init_config_flow(hass)
    MockConfigEntry(
        domain=config_flow.DOMAIN, data={config_flow.CONF_SERVER_IDENTIFIER: MOCK_ID_1}
    ).add_to_hass(hass)

    mock_connections = MockConnections()

    mm_plex_account = MagicMock()
    mm_plex_account.resources = Mock(return_value=[MOCK_SERVER_1])
    mm_plex_account.resource = Mock(return_value=mock_connections)

    with patch("plexapi.server.PlexServer") as mock_plex_server, asynctest.patch(
        "plexauth.PlexAuth.initiate_auth"
    ), asynctest.patch("plexauth.PlexAuth.token", return_value=MOCK_TOKEN):
        type(mock_plex_server.return_value).machineIdentifier = PropertyMock(
            return_value=MOCK_SERVER_1.clientIdentifier
        )
        type(mock_plex_server.return_value).friendlyName = PropertyMock(
            return_value=MOCK_SERVER_1.name
        )
        type(  # pylint: disable=protected-access
            mock_plex_server.return_value
        )._baseurl = PropertyMock(return_value=mock_connections.connections[0].httpuri)

        result = await flow.async_step_import(
            {CONF_TOKEN: MOCK_TOKEN, CONF_URL: f"http://{MOCK_HOST_1}:{MOCK_PORT_1}"}
        )
        assert result["type"] == "abort"
        assert result["reason"] == "already_configured"


async def test_all_available_servers_configured(hass):
    """Test when all available servers are already configured."""

    await async_setup_component(hass, "http", {"http": {}})

    MockConfigEntry(
        domain=config_flow.DOMAIN,
        data={
            config_flow.CONF_SERVER_IDENTIFIER: MOCK_ID_1,
            config_flow.CONF_SERVER: MOCK_NAME_1,
        },
    ).add_to_hass(hass)

    MockConfigEntry(
        domain=config_flow.DOMAIN,
        data={
            config_flow.CONF_SERVER_IDENTIFIER: MOCK_ID_2,
            config_flow.CONF_SERVER: MOCK_NAME_2,
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "start_website_auth"

    mock_connections = MockConnections()
    mm_plex_account = MagicMock()
    mm_plex_account.resources = Mock(return_value=[MOCK_SERVER_1, MOCK_SERVER_2])
    mm_plex_account.resource = Mock(return_value=mock_connections)

    with patch(
        "plexapi.myplex.MyPlexAccount", return_value=mm_plex_account
    ), asynctest.patch("plexauth.PlexAuth.initiate_auth"), asynctest.patch(
        "plexauth.PlexAuth.token", return_value=MOCK_TOKEN
    ):

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "external"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "external_done"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "abort"
        assert result["reason"] == "all_configured"


async def test_option_flow(hass):
    """Test config flow selection of one of two bridges."""

    entry = MockConfigEntry(domain=config_flow.DOMAIN, data={}, options=DEFAULT_OPTIONS)
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.flow.async_init(
        entry.entry_id, context={"source": "test"}, data=None
    )
    assert result["type"] == "form"
    assert result["step_id"] == "plex_mp_settings"

    result = await hass.config_entries.options.flow.async_configure(
        result["flow_id"],
        user_input={
            config_flow.CONF_USE_EPISODE_ART: True,
            config_flow.CONF_SHOW_ALL_CONTROLS: True,
        },
    )
    assert result["type"] == "create_entry"
    assert result["data"] == {
        config_flow.MP_DOMAIN: {
            config_flow.CONF_USE_EPISODE_ART: True,
            config_flow.CONF_SHOW_ALL_CONTROLS: True,
        }
    }


async def test_external_timed_out(hass):
    """Test when external flow times out."""

    await async_setup_component(hass, "http", {"http": {}})

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "start_website_auth"

    with asynctest.patch("plexauth.PlexAuth.initiate_auth"), asynctest.patch(
        "plexauth.PlexAuth.token", return_value=None
    ):

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "external"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "external_done"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "abort"
        assert result["reason"] == "token_request_timeout"


async def test_callback_view(hass, aiohttp_client):
    """Test callback view."""

    await async_setup_component(hass, "http", {"http": {}})

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "start_website_auth"

    with asynctest.patch("plexauth.PlexAuth.initiate_auth"), asynctest.patch(
        "plexauth.PlexAuth.token", return_value=MOCK_TOKEN
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "external"

        client = await aiohttp_client(hass.http.app)
        forward_url = f'{config_flow.AUTH_CALLBACK_PATH}?flow_id={result["flow_id"]}'

        resp = await client.get(forward_url)
        assert resp.status == 200

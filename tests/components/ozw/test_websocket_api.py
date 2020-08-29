"""Test OpenZWave Websocket API."""

from homeassistant.components.ozw.websocket_api import ID, NODE_ID, OZW_INSTANCE, TYPE

from .common import setup_ozw


async def test_websocket_api(hass, generic_data, hass_ws_client):
    """Test the ozw websocket api."""
    await setup_ozw(hass, fixture=generic_data)
    client = await hass_ws_client(hass)

    # Test network status
    await client.send_json({ID: 5, TYPE: "ozw/network_status"})
    msg = await client.receive_json()
    result = msg["result"]

    assert result["state"] == "driverAllNodesQueried"
    assert result[OZW_INSTANCE] == 1

    # Test node status
    await client.send_json({ID: 6, TYPE: "ozw/node_status", NODE_ID: 32})
    msg = await client.receive_json()
    result = msg["result"]

    assert result[OZW_INSTANCE] == 1
    assert result[NODE_ID] == 32
    assert result["node_query_stage"] == "Complete"
    assert result["is_zwave_plus"]
    assert result["is_awake"]
    assert not result["is_failed"]
    assert result["node_baud_rate"] == 100000
    assert result["is_beaming"]
    assert not result["is_flirs"]
    assert result["is_routing"]
    assert not result["is_securityv1"]
    assert result["node_basic_string"] == "Routing Slave"
    assert result["node_generic_string"] == "Binary Switch"
    assert result["node_specific_string"] == "Binary Power Switch"
    assert result["neighbors"] == [1, 33, 36, 37, 39]

    # Test node statistics
    await client.send_json({ID: 7, TYPE: "ozw/node_statistics", NODE_ID: 39})
    msg = await client.receive_json()
    result = msg["result"]

    assert result[OZW_INSTANCE] == 1
    assert result[NODE_ID] == 39
    assert result["send_count"] == 57
    assert result["sent_failed"] == 0
    assert result["retries"] == 1
    assert result["last_request_rtt"] == 26
    assert result["last_response_rtt"] == 38
    assert result["average_request_rtt"] == 29
    assert result["average_response_rtt"] == 37
    assert result["received_packets"] == 3594
    assert result["received_dup_packets"] == 12
    assert result["received_unsolicited"] == 3546

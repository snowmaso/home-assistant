"""The tests for the time automation."""
from datetime import timedelta

import pytest

import homeassistant.components.automation as automation
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.async_mock import Mock, patch
from tests.common import (
    assert_setup_component,
    async_fire_time_changed,
    async_mock_service,
    mock_component,
)


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


@pytest.fixture(autouse=True)
def setup_comp(hass):
    """Initialize components."""
    mock_component(hass, "group")


async def test_if_fires_using_at(hass, calls):
    """Test for firing at."""
    now = dt_util.utcnow()

    time_that_will_not_match_right_away = now.replace(
        year=now.year + 1, hour=4, minute=59, second=0
    )

    with patch(
        "homeassistant.util.dt.utcnow", return_value=time_that_will_not_match_right_away
    ):
        assert await async_setup_component(
            hass,
            automation.DOMAIN,
            {
                automation.DOMAIN: {
                    "trigger": {"platform": "time", "at": "5:00:00"},
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "{{ trigger.platform }} - {{ trigger.now.hour }}"
                        },
                    },
                }
            },
        )

    now = dt_util.utcnow()

    async_fire_time_changed(
        hass, now.replace(year=now.year + 1, hour=5, minute=0, second=0)
    )

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "time - 5"


async def test_if_fires_using_multiple_at(hass, calls):
    """Test for firing at."""

    now = dt_util.utcnow()

    time_that_will_not_match_right_away = now.replace(
        year=now.year + 1, hour=4, minute=59, second=0
    )

    with patch(
        "homeassistant.util.dt.utcnow", return_value=time_that_will_not_match_right_away
    ):
        assert await async_setup_component(
            hass,
            automation.DOMAIN,
            {
                automation.DOMAIN: {
                    "trigger": {"platform": "time", "at": ["5:00:00", "6:00:00"]},
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "{{ trigger.platform }} - {{ trigger.now.hour }}"
                        },
                    },
                }
            },
        )

    now = dt_util.utcnow()

    async_fire_time_changed(
        hass, now.replace(year=now.year + 1, hour=5, minute=0, second=0)
    )

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "time - 5"

    async_fire_time_changed(
        hass, now.replace(year=now.year + 1, hour=6, minute=0, second=0)
    )

    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[1].data["some"] == "time - 6"


async def test_if_not_fires_using_wrong_at(hass, calls):
    """YAML translates time values to total seconds.

    This should break the before rule.
    """
    now = dt_util.utcnow()

    time_that_will_not_match_right_away = now.replace(
        year=now.year + 1, hour=1, minute=0, second=0
    )

    with patch(
        "homeassistant.util.dt.utcnow", return_value=time_that_will_not_match_right_away
    ):
        with assert_setup_component(0, automation.DOMAIN):
            assert await async_setup_component(
                hass,
                automation.DOMAIN,
                {
                    automation.DOMAIN: {
                        "trigger": {
                            "platform": "time",
                            "at": 3605,
                            # Total seconds. Hour = 3600 second
                        },
                        "action": {"service": "test.automation"},
                    }
                },
            )

    async_fire_time_changed(
        hass, now.replace(year=now.year + 1, hour=1, minute=0, second=5)
    )

    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_if_action_before(hass, calls):
    """Test for if action before."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {"condition": "time", "before": "10:00"},
                "action": {"service": "test.automation"},
            }
        },
    )

    before_10 = dt_util.now().replace(hour=8)
    after_10 = dt_util.now().replace(hour=14)

    with patch("homeassistant.helpers.condition.dt_util.now", return_value=before_10):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()

    assert len(calls) == 1

    with patch("homeassistant.helpers.condition.dt_util.now", return_value=after_10):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()

    assert len(calls) == 1


async def test_if_action_after(hass, calls):
    """Test for if action after."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {"condition": "time", "after": "10:00"},
                "action": {"service": "test.automation"},
            }
        },
    )

    before_10 = dt_util.now().replace(hour=8)
    after_10 = dt_util.now().replace(hour=14)

    with patch("homeassistant.helpers.condition.dt_util.now", return_value=before_10):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()

    assert len(calls) == 0

    with patch("homeassistant.helpers.condition.dt_util.now", return_value=after_10):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()

    assert len(calls) == 1


async def test_if_action_one_weekday(hass, calls):
    """Test for if action with one weekday."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {"condition": "time", "weekday": "mon"},
                "action": {"service": "test.automation"},
            }
        },
    )

    days_past_monday = dt_util.now().weekday()
    monday = dt_util.now() - timedelta(days=days_past_monday)
    tuesday = monday + timedelta(days=1)

    with patch("homeassistant.helpers.condition.dt_util.now", return_value=monday):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()

    assert len(calls) == 1

    with patch("homeassistant.helpers.condition.dt_util.now", return_value=tuesday):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()

    assert len(calls) == 1


async def test_if_action_list_weekday(hass, calls):
    """Test for action with a list of weekdays."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {"condition": "time", "weekday": ["mon", "tue"]},
                "action": {"service": "test.automation"},
            }
        },
    )

    days_past_monday = dt_util.now().weekday()
    monday = dt_util.now() - timedelta(days=days_past_monday)
    tuesday = monday + timedelta(days=1)
    wednesday = tuesday + timedelta(days=1)

    with patch("homeassistant.helpers.condition.dt_util.now", return_value=monday):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()

    assert len(calls) == 1

    with patch("homeassistant.helpers.condition.dt_util.now", return_value=tuesday):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()

    assert len(calls) == 2

    with patch("homeassistant.helpers.condition.dt_util.now", return_value=wednesday):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()

    assert len(calls) == 2


async def test_untrack_time_change(hass):
    """Test for removing tracked time changes."""
    mock_track_time_change = Mock()
    with patch(
        "homeassistant.components.automation.time.async_track_time_change",
        return_value=mock_track_time_change,
    ):
        assert await async_setup_component(
            hass,
            automation.DOMAIN,
            {
                automation.DOMAIN: {
                    "alias": "test",
                    "trigger": {
                        "platform": "time",
                        "at": ["5:00:00", "6:00:00", "7:00:00"],
                    },
                    "action": {"service": "test.automation", "data": {"test": "test"}},
                }
            },
        )

    await hass.services.async_call(
        automation.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "automation.test"},
        blocking=True,
    )

    assert len(mock_track_time_change.mock_calls) == 3

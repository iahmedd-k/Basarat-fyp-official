from unittest.mock import MagicMock, patch
import pytest

from app.core.celery_beat import HeartbeatPersistentScheduler
from app.core.health import CELERY_BEAT_HEARTBEAT_KEY, CELERY_BEAT_HEARTBEAT_TTL_SECONDS


def test_heartbeat_scheduler_records_heartbeat_on_setup():
    mock_redis = MagicMock()
    with patch("app.core.celery_beat.get_sync_redis_client", return_value=mock_redis), \
         patch.object(HeartbeatPersistentScheduler, "setup_schedule", autospec=True) as orig_setup:
        
        # Instantiate scheduler
        scheduler = object.__new__(HeartbeatPersistentScheduler)
        HeartbeatPersistentScheduler.__init__(scheduler, app=MagicMock())
        
        scheduler._record_heartbeat()
        mock_redis.set.assert_called_with(
            CELERY_BEAT_HEARTBEAT_KEY,
            "1",
            ex=CELERY_BEAT_HEARTBEAT_TTL_SECONDS,
        )


def test_heartbeat_scheduler_tick_records_heartbeat():
    mock_redis = MagicMock()
    with patch("app.core.celery_beat.get_sync_redis_client", return_value=mock_redis):
        scheduler = object.__new__(HeartbeatPersistentScheduler)
        scheduler._last_heartbeat_time = 0.0
        
        # Calling _record_heartbeat directly
        scheduler._record_heartbeat()
        assert mock_redis.set.call_count == 1
        
        # Immediate subsequent tick should throttle (within 15s)
        with patch("celery.beat.PersistentScheduler.tick", return_value=1.0):
            scheduler.tick()
            assert mock_redis.set.call_count == 1


def test_heartbeat_scheduler_handles_redis_failure_gracefully():
    mock_redis = MagicMock()
    mock_redis.set.side_effect = ConnectionError("Redis down")
    with patch("app.core.celery_beat.get_sync_redis_client", return_value=mock_redis):
        scheduler = object.__new__(HeartbeatPersistentScheduler)
        scheduler._last_heartbeat_time = 0.0
        
        # Must not raise
        scheduler._record_heartbeat()

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cluster import Cluster
from app.models.cluster_alert import ClusterAlert
from app.services import alert_service


def _make_cluster(**overrides) -> Cluster:
    defaults = dict(
        name=f"test-cluster-{uuid.uuid4().hex[:8]}",
        topology="pss",
        mongodb_version="7.0",
        mongodb_port=37017,
        replicaset_name="rs0",
        config={},
        created_by=uuid.uuid4(),
    )
    defaults.update(overrides)
    return Cluster(**defaults)


@pytest.mark.asyncio
async def test_create_new_alert(db_session: AsyncSession):
    cluster = _make_cluster()
    db_session.add(cluster)
    await db_session.flush()

    alert, is_new = await alert_service.create_or_update_alert(
        db_session,
        cluster_id=cluster.id,
        metric="replication_lag",
        severity="warning",
        message="Replication lag exceeded threshold",
        threshold_value=5.0,
        actual_value=7.2,
    )

    assert is_new is True
    assert alert.status == "active"
    assert alert.metric == "replication_lag"
    assert alert.severity == "warning"
    assert alert.actual_value == 7.2


@pytest.mark.asyncio
async def test_update_existing_alert(db_session: AsyncSession):
    cluster = _make_cluster()
    db_session.add(cluster)
    await db_session.flush()

    alert1, is_new1 = await alert_service.create_or_update_alert(
        db_session,
        cluster_id=cluster.id,
        metric="connections",
        severity="warning",
        message="High connections",
        threshold_value=500.0,
        actual_value=550.0,
    )
    assert is_new1 is True

    alert2, is_new2 = await alert_service.create_or_update_alert(
        db_session,
        cluster_id=cluster.id,
        metric="connections",
        severity="critical",
        message="Very high connections",
        threshold_value=500.0,
        actual_value=820.0,
    )
    assert is_new2 is False
    assert alert2.id == alert1.id
    assert alert2.actual_value == 820.0
    assert alert2.severity == "critical"


@pytest.mark.asyncio
async def test_resolve_alert(db_session: AsyncSession):
    cluster = _make_cluster()
    db_session.add(cluster)
    await db_session.flush()

    await alert_service.create_or_update_alert(
        db_session,
        cluster_id=cluster.id,
        metric="disk_usage",
        severity="warning",
        message="Disk usage high",
        threshold_value=70.0,
        actual_value=75.0,
    )

    resolved = await alert_service.resolve_alert(db_session, cluster.id, "disk_usage")
    assert resolved is True

    active = await alert_service.get_active_alert(db_session, cluster.id, "disk_usage")
    assert active is None


@pytest.mark.asyncio
async def test_list_alerts_filtered(db_session: AsyncSession):
    cluster_a = _make_cluster()
    cluster_b = _make_cluster()
    db_session.add_all([cluster_a, cluster_b])
    await db_session.flush()

    await alert_service.create_or_update_alert(
        db_session,
        cluster_id=cluster_a.id,
        metric="replication_lag",
        severity="warning",
        message="Lag on A",
        threshold_value=5.0,
        actual_value=6.0,
    )
    await alert_service.create_or_update_alert(
        db_session,
        cluster_id=cluster_b.id,
        metric="connections",
        severity="critical",
        message="Connections on B",
        threshold_value=500.0,
        actual_value=900.0,
    )

    alerts_a = await alert_service.list_alerts(db_session, cluster_id=cluster_a.id)
    assert len(alerts_a) == 1
    assert alerts_a[0].cluster_id == cluster_a.id

    all_alerts = await alert_service.list_alerts(db_session)
    assert len(all_alerts) >= 2


@pytest.mark.asyncio
async def test_count_active_alerts(db_session: AsyncSession):
    cluster = _make_cluster()
    db_session.add(cluster)
    await db_session.flush()

    await alert_service.create_or_update_alert(
        db_session,
        cluster_id=cluster.id,
        metric="memory_usage",
        severity="warning",
        message="Memory high",
        threshold_value=80.0,
        actual_value=85.0,
    )

    count = await alert_service.count_active_alerts(db_session)
    assert count >= 1


@pytest.mark.asyncio
async def test_slack_debounce(db_session: AsyncSession, monkeypatch):
    # With no webhook URL, should_notify_slack returns False
    monkeypatch.setattr("app.services.alert_service.settings", _FakeSettings(webhook=""))
    alert = ClusterAlert(
        cluster_id=uuid.uuid4(),
        metric="test",
        severity="warning",
        message="test",
        threshold_value=1.0,
        actual_value=2.0,
        status="active",
    )
    assert alert_service.should_notify_slack(alert) is False

    # With webhook URL set and notified_at=None -> True
    monkeypatch.setattr(
        "app.services.alert_service.settings", _FakeSettings(webhook="https://hooks.slack.com/test")
    )
    assert alert_service.should_notify_slack(alert) is True

    # notified_at within debounce window -> False
    alert.notified_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    assert alert_service.should_notify_slack(alert) is False

    # notified_at outside debounce window -> True
    alert.notified_at = datetime.now(timezone.utc) - timedelta(minutes=20)
    assert alert_service.should_notify_slack(alert) is True


class _FakeSettings:
    def __init__(self, webhook: str = "", debounce: int = 15):
        self.SLACK_WEBHOOK_URL = webhook
        self.ALERT_DEBOUNCE_MINUTES = debounce

import asyncio
import logging

from sqlalchemy import select

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.cluster import Cluster
from app.services import monitor_service

logger = logging.getLogger(__name__)


async def poll_all_clusters() -> None:
    async with async_session_factory() as db:
        result = await db.execute(select(Cluster).where(Cluster.status != "pending"))
        clusters = list(result.scalars().all())
        for cluster in clusters:
            try:
                metric = await monitor_service.collect_cluster_metrics(db, cluster)
                if metric:
                    await monitor_service.check_thresholds_and_alert(db, cluster, metric)
                    await monitor_service.update_cluster_status(db, cluster, metric)
                await db.commit()
            except Exception as e:
                logger.error(f"Error polling cluster {cluster.name}: {e}")
                await db.rollback()


async def poller_loop() -> None:
    logger.info(f"Poller started (interval: {settings.POLLER_INTERVAL_SECONDS}s)")
    while True:
        if settings.POLLER_ENABLED:
            try:
                await poll_all_clusters()
            except Exception as e:
                logger.error(f"Poller cycle error: {e}")
        await asyncio.sleep(settings.POLLER_INTERVAL_SECONDS)

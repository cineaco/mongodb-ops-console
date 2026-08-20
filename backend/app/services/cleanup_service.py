import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.cluster_metric import ClusterMetric

logger = logging.getLogger(__name__)


async def cleanup_old_metrics() -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.METRICS_RETENTION_DAYS)
    async with async_session_factory() as db:
        result = await db.execute(delete(ClusterMetric).where(ClusterMetric.collected_at < cutoff))
        await db.commit()
        count = result.rowcount
        if count > 0:
            logger.info(f"Cleaned up {count} metric rows older than {settings.METRICS_RETENTION_DAYS} days")
        return count


async def cleanup_loop() -> None:
    logger.info(f"Cleanup task started (retention: {settings.METRICS_RETENTION_DAYS} days)")
    while True:
        try:
            await cleanup_old_metrics()
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
        await asyncio.sleep(86400)

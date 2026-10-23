"""Non-blocking cache warm-up so the first user request is fast."""

from __future__ import annotations

import structlog

logger = structlog.get_logger()


def warm_caches() -> None:
    try:
        from api.routes.main import warm_road_index

        if warm_road_index():
            logger.info("Road risk index warm")
    except Exception as exc:
        logger.warning("Road index warm-up skipped", error=str(exc))

    try:
        from api.routes.lite import warm as warm_lite

        warm_lite()
        logger.info("Ward lite shapes warm")
    except Exception as exc:
        logger.warning("Ward lite warm-up skipped", error=str(exc))

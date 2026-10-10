"""匿名统计控制器（MVC —— Controller 层，04-1 §九 / 03-2 §7.5）。

⚠️ 隐私红线：`stats_events` 只存聚合计数，**不得出现 account_id / child_id / client_id**。
落库维度仅：event_name × content_ref × client × device_form × client_version × bucket_date。
客户端已本地聚合到小时桶，服务端 `$inc` 累加即可（聚合逻辑在 StatsEventRepository）。
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..repositories import Repositories


async def ingest(repos: Repositories, events: list) -> dict:
    accepted = await repos.stats_events.ingest(events, now=datetime.now(timezone.utc))
    return {"accepted": accepted}

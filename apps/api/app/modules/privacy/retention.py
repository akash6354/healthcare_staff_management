"""Run retention for every hospital: `uv run python -m app.modules.privacy.retention`."""

import asyncio

from app.core.db import dispose_engines, tenant_session
from app.modules.platform.service import list_hospitals
from app.modules.privacy.service import apply_retention


async def main() -> dict[str, int]:
    totals = {"photos_purged": 0, "staff_anonymised": 0}
    for hid, code in await list_hospitals():
        async with tenant_session(hid) as s:
            stats = await apply_retention(s, hid)
        print(f"{code}: {stats}")
        for k, v in stats.items():
            totals[k] += v
    await dispose_engines()
    return totals


if __name__ == "__main__":
    asyncio.run(main())

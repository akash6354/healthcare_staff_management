"""`make verify-audit`: re-hash every hospital's audit chain and report the first broken link."""

import asyncio
import sys

from app.audit.service import verify_chain
from app.core.db import dispose_engines, tenant_session
from app.modules.platform.service import list_hospitals


async def main() -> int:
    hospitals = await list_hospitals()
    failed = 0
    for hid, code in hospitals:
        async with tenant_session(hid) as s:
            result = await verify_chain(s, hid)
        status = "OK " if result.ok else "BAD"
        detail = "" if result.ok else f" first bad seq={result.first_bad_seq} ({result.reason})"
        print(f"{status} {code}: {result.events} events{detail}")
        failed += 0 if result.ok else 1
    await dispose_engines()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

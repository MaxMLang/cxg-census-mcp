"""``python -m cxg_census_mcp.metrics_dump`` → Prometheus text on stdout."""

from __future__ import annotations

import sys

from cxg_census_mcp.metrics import render_prometheus


def main() -> int:
    sys.stdout.write(render_prometheus())
    return 0


if __name__ == "__main__":
    sys.exit(main())

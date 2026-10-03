"""Run one fundamentals refresh from a process with a safe multiprocessing entrypoint."""

from __future__ import annotations

import argparse

from app.tasks.refresh_fundamentals import refresh_fundamentals


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("symbols", nargs="*", help="Optional symbols; defaults to the frozen KSE-100 universe.")
    args = parser.parse_args()
    result = refresh_fundamentals.run(args.symbols or None)
    print(result)


if __name__ == "__main__":
    main()

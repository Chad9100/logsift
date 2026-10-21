#!/usr/bin/env python3
"""Measure logsift's throughput and memory use on synthetic access logs.

Not part of the installed package: a development tool for checking the
"streams large logs instead of loading every request into memory" claim in
the README. Generates Combined Log Format lines on the fly (nothing is
committed to the repo), runs them through the real parsing/aggregation path,
and reports lines/sec, MB/sec and the peak additional Python-heap memory
used while processing, measured with tracemalloc.

Usage:
    python scripts/benchmark.py                  # default sizes
    python scripts/benchmark.py 10000 1000000    # custom line counts
"""

from __future__ import annotations

import gc
import os
import sys
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from logsift.cli import main as cli_main  # noqa: E402
from logsift.stats import stream_summarize  # noqa: E402

# Cycling through a fixed, modest number of distinct values (not one unique
# value per line) is what the streaming claim is actually about: memory
# should track this cardinality, not the total line count.
DISTINCT_PATHS = 500
DISTINCT_IPS = 2000
AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0)",
    "curl/8.5.0",
]


def make_line(i: int) -> str:
    ip_num = i % DISTINCT_IPS
    ip = f"10.{(ip_num >> 16) & 255}.{(ip_num >> 8) & 255}.{ip_num & 255}"
    path = i % DISTINCT_PATHS
    status = 200 if i % 10 else 404
    agent = AGENTS[i % len(AGENTS)]
    return (
        f'{ip} - - [19/Oct/2026:08:00:00 +0000] "GET /item/{path} HTTP/1.1" '
        f'{status} 512 "-" "{agent}"\n'
    )


def lines(n: int):
    for i in range(n):
        yield make_line(i)


def human_mb(n_bytes: int) -> float:
    return n_bytes / (1024 * 1024)


def _silence_stdout():
    return open(os.devnull, "w", encoding="utf-8")


def bench_in_memory(n: int) -> None:
    """Pure aggregation: no disk I/O, just parsing + counting.

    Timing and memory are measured in separate runs: tracemalloc's own
    instrumentation overhead (observed at roughly 40-50x here) would make
    the timed run meaningless as a throughput number if both were measured
    together.
    """
    gc.collect()
    start = time.perf_counter()
    stream_summarize(lines(n))
    elapsed = time.perf_counter() - start

    gc.collect()
    tracemalloc.start()
    summary = stream_summarize(lines(n))
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print(f"  in-memory, {n:>9,} lines: {elapsed:6.2f}s  "
          f"{n / elapsed:>10,.0f} lines/s  peak extra mem: {human_mb(peak):6.2f} MB  "
          f"(distinct paths counted: {len(summary.paths)})")


def bench_from_file(n: int, tmp_dir: Path) -> None:
    """End-to-end: write a real file, then run it through the actual CLI path."""
    path = tmp_dir / f"bench_{n}.log"
    with open(path, "w", encoding="utf-8") as fh:
        fh.writelines(lines(n))
    size_mb = human_mb(path.stat().st_size)

    gc.collect()
    start = time.perf_counter()
    old_stdout = sys.stdout
    sys.stdout = _silence_stdout()
    try:
        cli_main([str(path), "--format", "json"])
    finally:
        sys.stdout.close()
        sys.stdout = old_stdout
    elapsed = time.perf_counter() - start

    gc.collect()
    tracemalloc.start()
    old_stdout = sys.stdout
    sys.stdout = _silence_stdout()
    try:
        cli_main([str(path), "--format", "json"])
    finally:
        sys.stdout.close()
        sys.stdout = old_stdout
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    path.unlink()

    print(f"  from file, {n:>9,} lines ({size_mb:6.1f} MB): {elapsed:6.2f}s  "
          f"{n / elapsed:>10,.0f} lines/s  {size_mb / elapsed:6.1f} MB/s  "
          f"peak extra mem: {human_mb(peak):6.2f} MB")


def main() -> None:
    sizes = [int(a) for a in sys.argv[1:]] or [10_000, 100_000, 1_000_000]
    print(f"Python {sys.version.split()[0]} on {sys.platform}\n")

    print("stream_summarize() directly (no file I/O):")
    for n in sizes:
        bench_in_memory(n)

    print("\nFull CLI path, reading a real file on disk:")
    tmp_dir = Path(__file__).resolve().parent.parent / ".bench_tmp"
    tmp_dir.mkdir(exist_ok=True)
    try:
        for n in sizes:
            bench_from_file(n, tmp_dir)
    finally:
        tmp_dir.rmdir()


if __name__ == "__main__":
    main()

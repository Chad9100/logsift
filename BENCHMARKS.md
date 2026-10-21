# Benchmarks

Measured with [scripts/benchmark.py](scripts/benchmark.py) on synthetic Combined Log
Format access logs with 500 distinct paths and 2,000 distinct IPs repeated across the
requested number of lines (not one unique value per line — the whole point of the
streaming claim is about distinct-value cardinality, not line count). Timing and peak
memory are measured in separate runs; [tracemalloc](https://docs.python.org/3/library/tracemalloc.html)'s
own instrumentation overhead made the first combined attempt at this show throughput
roughly 40-50x slower than real, so it's no longer measured alongside timing.

**Environment:** Python 3.12.10, Windows, single run, default CPython (no PyPy/JIT).
These are relative, order-of-magnitude numbers for this machine, not a guarantee of
throughput on any other hardware; reruns vary by roughly ±10%.

## Throughput

| Lines     | File size | Time   | Lines/s | MB/s |
|-----------|-----------|--------|---------|------|
| 10,000    | 1.1 MB    | 0.32s  | 31,445  | 3.5  |
| 100,000   | 11.1 MB   | 3.04s  | 32,903  | 3.6  |
| 1,000,000 | 110.6 MB  | 32.12s | 31,134  | 3.4  |

Throughput stays essentially flat from 10,000 to 1,000,000 lines, as expected for the
single-pass, O(n) design: there's no step that gets slower as the file grows.

## Memory

| Lines     | Peak extra memory (stream_summarize) | Peak extra memory (full CLI run) |
|-----------|---------------------------------------|-----------------------------------|
| 10,000    | 0.35 MB                                | 0.42 MB                            |
| 100,000   | 0.35 MB                                | 0.42 MB                            |
| 1,000,000 | 0.43 MB                                | 0.50 MB                            |

This is the number the "streams large logs instead of loading every request into
memory first" claim in the README is actually about: peak memory barely moves from
10,000 lines to 1,000,000 (a 100x increase in requests), because it tracks 500 distinct
paths and 2,000 distinct IPs either way, not one entry per request. A log with a much
higher cardinality of distinct values (for example, millions of unique paths) would use
correspondingly more memory for those counts, since they do have to be kept; that's
inherent to producing per-path/per-IP statistics at all, not something `--follow` or any
output format changes.

## Running it yourself

```
python scripts/benchmark.py                  # default sizes: 10k, 100k, 1M lines
python scripts/benchmark.py 50000 500000     # custom line counts
```

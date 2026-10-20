# logsift

**logsift** is a small, dependency-free command-line tool that turns Apache and Nginx
access logs into a readable summary: request counts, top pages, top visitors, status
codes, error hot spots and user agents.

It's for people who run their own websites, home servers or small VPSes and want a
quick answer to "what's hitting my server?" without setting up a full analytics stack.

Built with Python 3.10+ (standard library only), tested with pytest.

> Status: early development (v0.1). See [ROADMAP.md](ROADMAP.md) for what's planned.

## Features

- Parses **Common** and **Combined** Log Format (Apache and Nginx defaults)
- Reads plain files, **`.gz`** rotated logs, several files at once, or **stdin**
- Text report, **JSON** for scripting, or **CSV** for spreadsheets (`--format csv`)
- **Colored output** in a terminal (errors in red, status classes by color); automatically
  off when piped, when `NO_COLOR` is set, or with `--color never`
- **Requests-over-time** bar chart, per minute / hour / day (`--bucket`, picked automatically by default)
- **Bandwidth reports**: which pages and which visitors use the most data
- **Bot detection**: shows how much traffic comes from crawlers, monitors and scripts
  (Googlebot, AhrefsBot, curl, python-requests, ...); `--exclude-bots` / `--only-bots`
- **Path grouping**: query strings are stripped so `/search?q=a` and `/search?q=b` count
  as one page (`--keep-query` to keep them); `--group-ids` merges IDs, so `/items/123`
  and `/items/456` become `/items/:id`
- Filters: `--status 404,5xx`, `--since` / `--until` time windows, `--top N`
- Counts and reports lines it couldn't parse instead of crashing

## Install

```bash
git clone https://github.com/Chad9100/logsift.git
cd logsift
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -e .
```

## Usage

```bash
logsift examples/sample_access.log
logsift /var/log/nginx/access.log /var/log/nginx/access.log.1.gz --top 5
logsift access.log --status 5xx --since 2026-10-19T09:00
logsift access.log --bucket day         # one chart row per day
logsift access.log --exclude-bots       # human visitors only
logsift access.log --group-ids          # /items/123 and /items/456 -> /items/:id
logsift access.log --color always | less -R   # keep colors when paging
logsift access.log --format csv > report.csv  # open in a spreadsheet
cat access.log | logsift --format json
python -m logsift access.log            # same thing without the script
```

Example output (trimmed):

```
Requests:      13
Unique IPs:    5
Data sent:     25.6 KB
Error rate:    46.2%
Bot traffic:   6 (46.2%)

Status classes
  2xx: 6
  3xx: 1
  4xx: 5
  5xx: 1

Requests over time (per hour)
  2026-10-19 08:00  4  ########################################
  2026-10-19 09:00  3  ##############################
  2026-10-19 10:00  2  ####################
  2026-10-19 11:00  2  ####################
  2026-10-19 12:00  1  ##########
  2026-10-19 13:00  1  ##########

Top IPs
  4   30.8%  203.0.113.25
  3   23.1%  192.0.2.10
```

`--format csv` writes every table (top paths, IPs, bandwidth, status codes, error
paths, user agents, bots, and the timeline) into one CSV, tagged by a `section`
column, so you can filter or pivot on it in a spreadsheet.

Run `logsift --help` for all options.

## Development

```bash
pip install -e ".[dev]"
pytest
```

The sample log in `examples/` is made up and uses reserved documentation IP ranges
(192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24). Real logs contain visitors' IP
addresses, so don't commit them; `.gitignore` excludes `*.log` outside `examples/`.

## License

[MIT](LICENSE)

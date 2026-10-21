# logsift

**logsift** is a small, dependency-free command-line tool that turns Apache and Nginx
access logs into a readable summary: request counts, top pages, top visitors, status
codes, error hot spots and user agents.

It's for people who run their own websites, home servers or small VPSes and want a
quick answer to "what's hitting my server?" without setting up a full analytics stack.

Built with Python 3.10+ (standard library only), tested with pytest.

> Status: early development (v0.1). See [ROADMAP.md](ROADMAP.md) for what's planned.

## Features

- Parses **Common** and **Combined** access log format (Apache and Nginx defaults),
  **JSON-lines access logs** (Caddy, Traefik, or a custom JSON log_format;
  auto-detected, mixed freely with CLF lines), and **Nginx error logs**
  (`--log-type error`)
- Reads plain files, **`.gz`** rotated logs, several files at once, or **stdin**
- Text report, **JSON** for scripting, **CSV** for spreadsheets, or a **self-contained
  HTML report** with charts (`--format html`; no external assets or JavaScript)
- **`--follow`**: watch growing log files and refresh the report live, like `tail -f`
  with a dashboard
- **Streams large logs** instead of loading every request into memory first, so a
  multi-gigabyte access log can be summarized without running out of RAM —
  see [BENCHMARKS.md](BENCHMARKS.md)
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

Not yet published to PyPI — see [PUBLISHING.md](PUBLISHING.md) for what's left to
do that. Until then, install from source:

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
logsift /var/log/nginx/error.log --log-type error   # levels, top messages, top clients
logsift examples/sample_access.jsonl                # JSON-lines logs work the same way
logsift access.log --format html > report.html      # open the file in a browser
logsift /var/log/nginx/access.log --follow           # live dashboard, Ctrl+C to stop
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

### Follow mode

`--follow` (`-F`) shows the existing report and then keeps it updated as new lines
are appended, refreshing every `--interval` seconds (default 2) until you press
Ctrl+C. It works on real files only, not stdin or `.gz`, and only with the default
text format. All the usual filters (`--status`, `--since`, `--exclude-bots`, ...)
still apply. A log rotated by renaming or shrinking in place is picked up
automatically; a same-size-or-larger rotation can't be told apart from normal
growth, a limitation shared by any simple polling-based tail.

### HTML report

`--format html` writes one self-contained HTML file: summary cards, a status-class
breakdown, a requests-over-time chart (inline SVG, with a tooltip per bar), and every
table from the text report, with status codes colored by class. There's no
JavaScript, no external stylesheet or font, and it follows your system's light/dark
theme. Values from the log are HTML-escaped, so a log with unusual content in it
can't inject markup into the report. Not yet available for `--log-type error`.

### JSON-lines access logs

If a line doesn't match Common/Combined Log Format but starts with `{`, logsift
tries to read it as one JSON object per line, and recognizes the common field
names used by Caddy, Traefik and custom JSON `log_format` configurations:
`time`/`ts`/`timestamp`/`StartUTC` for the timestamp (ISO 8601 or Unix epoch),
`remote_addr`/`client_ip`/`ip`/`ClientHost` for the IP, `method`/`path`/`protocol`
(or a combined `"request": "GET /x HTTP/1.1"` string) or their Caddy/Traefik
equivalents, `status`/`DownstreamStatus`, `size`/`bytes`/`DownstreamContentSize`,
`referer`, and `user_agent`. CLF and JSON lines can be mixed in the same file.
A line is only counted as unparseable if neither format matches it.

### Nginx error logs

`--log-type error` switches to a separate report: entry counts by severity level
(`debug` to `emerg`), the most common messages (grouped by replacing quoted paths
and numbers, so the same error from different requests counts as one), the busiest
client IPs, and the requests involved. Only `--since`, `--until`, `--top`,
`--format` and `--color` apply in this mode; the access-log-only options
(`--status`, `--group-ids`, `--exclude-bots`, ...) are ignored.

```
logsift error.log --log-type error --format json
```

Run `logsift --help` for all options.

### Large logs

The default (non-`--follow`) run processes each file in a single streaming pass:
it never holds a list of every parsed request, only the running counts, so the
memory it uses depends on how many *distinct* paths, IPs, status codes, and so on
appear in the log, not on how many requests there are. A log with a huge number of
requests to a modest number of distinct pages summarizes in roughly constant
memory; one with equally huge cardinality (millions of unique paths or IPs) will
still use memory proportional to that, since the counts themselves have to be
kept. See [BENCHMARKS.md](BENCHMARKS.md) for measured throughput and memory numbers.

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

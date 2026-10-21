# Roadmap

## v0.1 — done

- [x] Parse Common and Combined Log Format
- [x] Plain, `.gz`, multiple files and stdin input
- [x] Text and JSON reports
- [x] `--status`, `--since`, `--until`, `--top` filters
- [x] Tests and CI

## v0.2 — better reports

- [x] Requests-over-time histogram (per minute / hour / day) in the terminal
- [x] Group paths: strip query strings, optionally collapse IDs (`/items/123` → `/items/:id`)
- [x] Bot / crawler detection from user agents, with `--exclude-bots`
- [x] Bandwidth by path and by IP
- [x] Colored terminal output (auto-off when piped)

## v0.3 — more formats

- [ ] Custom log formats via Nginx `log_format` / Apache `LogFormat` strings
- [x] Nginx error log support
- [x] JSON-lines access logs (Caddy, Traefik)
- [x] CSV export

## v0.4 — dashboards and live mode

- [x] Self-contained HTML report with charts
- [x] `--follow` mode that tails a log and refreshes the summary
- [ ] Streaming aggregation so very large logs don't need to fit in memory

## v1.0 — release

- [ ] Publish to PyPI
- [ ] Documentation site with recipes
- [ ] Benchmarks on large logs

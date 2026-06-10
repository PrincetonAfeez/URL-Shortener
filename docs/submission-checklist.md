# Submission Checklist

Run this on a **fresh clone** before hand-in.

## Install

- [ ] `python -m pip install -e .[dev] -c requirements-lock.txt`
- [ ] `python -m pytest` — all green, coverage ≥ 80%

## CLI-first shared DB path

- [ ] `sniplink init-db`
- [ ] `sniplink create https://example.com --alias demo`
- [ ] `python web/manage.py migrate --fake-initial`
- [ ] `python web/manage.py runserver` — dashboard shows `demo`

## Protocol demos

- [ ] `sniplink serve-raw --port 9000` + `curl -v http://localhost:9000/demo`
- [ ] `sniplink serve-wsgi --port 9100` + `curl -v http://localhost:9100/demo`
- [ ] `curl -v -X HEAD http://localhost:9000/demo` — no click increment
- [ ] Disable link + `curl -v` → `410 Gone`

## API

- [ ] `POST /api/links` → `201` + `Location`
- [ ] Duplicate alias → `409`
- [ ] Optional: `SNIPLINK_API_KEY` + Bearer header

## Artifacts

- [ ] `docs/protocol-evidence.md` matches live `curl` output
- [ ] `docs/demo-script.md` rehearsed (or screen recording backup)
- [ ] `git tag v1.0-capstone` on submission commit
- [ ] CI green on GitHub (Python 3.11 + 3.12)

## Defense

- [ ] Read `docs/architecture.md` elevator pitch
- [ ] Read `docs/defense-faq.md`
- [ ] Read README **Known limitations**

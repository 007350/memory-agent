## What this changes

<!-- One or two sentences. Link the issue if there is one: Closes #123 -->

## Type

- [ ] Bug fix
- [ ] New feature / agent
- [ ] Refactor (no behaviour change)
- [ ] Docs
- [ ] Tests / CI

## How it was verified

<!-- Paste the commands you ran, not just "tests pass" -->

```bash
cd backend && python -m pytest tests/ --ignore=tests/evaluation -q
```

- [ ] Unit tests pass locally
- [ ] New behaviour is covered by a test (or: this is a docs-only change)
- [ ] The app still imports: `cd backend && python -c "import app.main"`

## Checklist

- [ ] No secrets, keys, `.env` files, `memory.db` or local agent directories added
- [ ] I did not refactor unrelated code
- [ ] Chinese and English README stay consistent if user-facing behaviour changed

# claude-token-tracker

Automatic token usage and cost tracking for the Anthropic Claude API. Drop-in replacement for the Anthropic SDK client that logs every API call — with zero changes to your existing code.

## Features

- **Zero setup** — works out of the box with SQLite or JSON (no server needed)
- **Drop-in replacement** — swap one import, everything else stays the same
- **Automatic tracking** — intercepts `messages.create()` and `messages.stream()` transparently
- **Multiple backends** — JSON, SQLite (default), MySQL, Excel, or all at once
- **Cost calculation** — built-in pricing for all Claude models (configurable)
- **Sync + Async** — supports both `Anthropic` and `AsyncAnthropic` clients
- **Non-blocking** — writes happen in background threads by default
- **Never breaks your app** — all tracking is wrapped in try/except

## Installation

```bash
# Basic install (SQLite backend — no extra dependencies)
pip install claude-token-tracker

# With MySQL support
pip install claude-token-tracker[mysql]

# With Excel support
pip install claude-token-tracker[excel]

# Everything
pip install claude-token-tracker[all]
```

Or install from source:

```bash
git clone https://github.com/prameshanu/claude-token-tracker.git
cd claude-token-tracker
pip install -e ".[all]"
```

## Quick Start

### Simplest usage (SQLite — zero config)

```python
# Before
import anthropic
client = anthropic.AsyncAnthropic(api_key="sk-...")

# After
from claude_token_tracker import TrackedAsyncAnthropic
client = TrackedAsyncAnthropic(api_key="sk-...", project="my_app", task_label="generate")
```

That's it. All your existing `client.messages.create(...)` and `async with client.messages.stream(...)` calls work unchanged. Usage is logged to `~/.claude_token_tracker/usage.db` automatically.

### Query your usage

```python
import sqlite3
conn = sqlite3.connect("~/.claude_token_tracker/usage.db")
for row in conn.execute("SELECT model, SUM(input_tokens), SUM(output_tokens), SUM(total_cost) FROM claude_token_usage GROUP BY model"):
    print(row)
```

## Storage Backends

| Backend | Setup Required | Install | Best For |
|---|---|---|---|
| **JSON** | None | `pip install claude-token-tracker` | Simplest possible, human-readable logs |
| **SQLite** (default) | None | `pip install claude-token-tracker` | Local development, queryable data |
| **MySQL** | MySQL server | `pip install claude-token-tracker[mysql]` | Production, team dashboards |
| **Excel** | None | `pip install claude-token-tracker[excel]` | Sharing reports, non-technical users |
| **All** | MySQL server | `pip install claude-token-tracker[all]` | Logging to everything at once |

### Switch backends via environment variable

```bash
# JSON (simplest — just a file with one JSON object per line)
export CLAUDE_TRACKER_STORAGE=json

# SQLite (default — no config needed)
export CLAUDE_TRACKER_STORAGE=sqlite

# MySQL
export CLAUDE_TRACKER_STORAGE=mysql
export CLAUDE_TRACKER_MYSQL_HOST=your-mysql-host
export CLAUDE_TRACKER_MYSQL_USER=your_user
export CLAUDE_TRACKER_MYSQL_PASSWORD=your_password
export CLAUDE_TRACKER_MYSQL_DATABASE=claude_tracker

# Excel only
export CLAUDE_TRACKER_STORAGE=excel
export CLAUDE_TRACKER_EXCEL_PATH=/path/to/usage.xlsx

# All backends at once
export CLAUDE_TRACKER_STORAGE=all
```

### JSON backend

The simplest option — each API call appends one JSON line to `~/.claude_token_tracker/usage.jsonl`:

```python
from claude_token_tracker import TrackedAsyncAnthropic, TrackerConfig
config = TrackerConfig(storage_backend="json")
client = TrackedAsyncAnthropic(api_key="sk-...", tracker_config=config, project="my_app")
```

Read it with any tool:
```python
import json
with open("~/.claude_token_tracker/usage.jsonl") as f:
    entries = [json.loads(line) for line in f]
print(f"Total cost: ${sum(e['total_cost'] for e in entries):.4f}")
```

## Excel Support

### Real-time logging to Excel

```bash
export CLAUDE_TRACKER_STORAGE=excel
export CLAUDE_TRACKER_EXCEL_PATH=/path/to/usage.xlsx
```

### Export MySQL data to Excel

```python
from claude_token_tracker import export_from_mysql
path = export_from_mysql(output_path="report.xlsx")
```

### CLI export

```bash
claude-tracker-export -o report.xlsx
```

## Configuration

All settings can be configured via environment variables or by passing a `TrackerConfig` object:

| Environment Variable | Default | Description |
|---|---|---|
| `CLAUDE_TRACKER_STORAGE` | `sqlite` | Backend: `json`, `sqlite`, `mysql`, `excel`, or `all` |
| `CLAUDE_TRACKER_JSON_PATH` | `~/.claude_token_tracker/usage.jsonl` | JSON lines file path |
| `CLAUDE_TRACKER_SQLITE_PATH` | `~/.claude_token_tracker/usage.db` | SQLite database file path |
| `CLAUDE_TRACKER_MYSQL_HOST` | `localhost` | MySQL server host |
| `CLAUDE_TRACKER_MYSQL_PORT` | `3306` | MySQL server port |
| `CLAUDE_TRACKER_MYSQL_USER` | `""` | MySQL username |
| `CLAUDE_TRACKER_MYSQL_PASSWORD` | `""` | MySQL password |
| `CLAUDE_TRACKER_MYSQL_DATABASE` | `claude_tracker` | MySQL database name |
| `CLAUDE_TRACKER_EXCEL_PATH` | `claude_token_usage.xlsx` | Excel file path |
| `CLAUDE_TRACKER_PRICING_URL` | GitHub raw URL | Remote pricing.json URL |
| `CLAUDE_TRACKER_PRICING_REFRESH_DAYS` | `7` | Days between pricing refreshes |
| `CLAUDE_TRACKER_ALERT_EMAIL` | `""` | Email for fetch failure alerts |
| `CLAUDE_TRACKER_SMTP_HOST` | `smtp.gmail.com` | SMTP server |
| `CLAUDE_TRACKER_SMTP_PORT` | `587` | SMTP port |
| `CLAUDE_TRACKER_SMTP_USER` | `""` | SMTP username |
| `CLAUDE_TRACKER_SMTP_PASSWORD` | `""` | SMTP password / app password |
| `CLAUDE_TRACKER_DEFAULT_PROJECT` | `""` | Default project label for all logs |
| `CLAUDE_TRACKER_DEFAULT_TASK_LABEL` | `""` | Default task label for all logs |
| `CLAUDE_TRACKER_AUTO_CREATE_TABLE` | `true` | Auto-create tables on first use |
| `CLAUDE_TRACKER_POOL_SIZE` | `5` | MySQL connection pool size |

### Programmatic configuration

```python
from claude_token_tracker import TrackedAsyncAnthropic, TrackerConfig

# SQLite (simplest)
client = TrackedAsyncAnthropic(api_key="sk-...", project="my_app")

# MySQL
config = TrackerConfig(
    storage_backend="mysql",
    mysql_host="your-mysql-host",
    mysql_user="tracker",
    mysql_password="secret",
    mysql_database="claude_tracker",
)
client = TrackedAsyncAnthropic(api_key="sk-...", tracker_config=config, project="my_app")

# All backends at once
config = TrackerConfig(
    storage_backend="all",
    mysql_host="your-mysql-host",
    mysql_user="tracker",
    mysql_password="secret",
    excel_path="usage.xlsx",
)
client = TrackedAsyncAnthropic(api_key="sk-...", tracker_config=config, project="my_app")
```

## What Gets Tracked

Every API call logs:

| Field | Description |
|---|---|
| `request_id` | Anthropic API request ID |
| `model` | Model used (e.g., `claude-sonnet-4-20250514`) |
| `input_tokens` | Tokens in the prompt |
| `output_tokens` | Tokens in the response |
| `total_tokens` | Sum of input + output |
| `cache_read_tokens` | Prompt caching: tokens read from cache |
| `cache_creation_tokens` | Prompt caching: tokens written to cache |
| `input_cost` | Input cost in USD (includes cache write/read costs) |
| `output_cost` | Output cost in USD |
| `total_cost` | Total cost in USD |
| `task_label` | Custom label (e.g., "generate_post") |
| `project` | Project name (e.g., "SM_connect") |
| `method` | `create` or `stream` |
| `duration_ms` | Wall clock time in milliseconds |
| `created_at` | Timestamp |

## Per-call task labels

Override the default task label on individual calls:

```python
# Uses default task_label from client init
message = await client.messages.create(model="claude-sonnet-4-20250514", ...)

# Override for this specific call
message = await client.messages.create(model="claude-sonnet-4-20250514", task_label="summarize", ...)
```

## Pricing — Auto-Refreshed

Pricing is automatically fetched from the [`pricing.json`](pricing.json) file in this repo and cached locally for 7 days. No manual updates needed.

**How it works:**
1. On first use, fetches `pricing.json` from GitHub
2. Caches at `~/.claude_token_tracker/pricing_cache.json`
3. Re-fetches every 7 days automatically
4. Falls back to hardcoded defaults if offline
5. Sends email alert if fetch fails (optional)

**Priority:** `pricing_overrides` (config) > remote `pricing.json` > local cache > hardcoded defaults

### Email alerts on pricing fetch failure

```bash
export CLAUDE_TRACKER_ALERT_EMAIL=you@example.com
export CLAUDE_TRACKER_SMTP_HOST=smtp.gmail.com
export CLAUDE_TRACKER_SMTP_PORT=587
export CLAUDE_TRACKER_SMTP_USER=you@gmail.com
export CLAUDE_TRACKER_SMTP_PASSWORD=your_app_password
```

### Custom pricing overrides (highest priority)

```python
config = TrackerConfig(
    pricing_overrides={
        "my-custom-model": {"input_per_mtok": 2.00, "output_per_mtok": 10.00}
    }
)
```

### Current pricing (USD per million tokens)

| Model | Input | Output | Cache Write | Cache Read |
|---|---|---|---|---|
| Opus 4.6 | $5.00 | $25.00 | $6.25 | $0.50 |
| Sonnet 4.6 | $3.00 | $15.00 | $3.75 | $0.30 |
| Haiku 4.5 | $1.00 | $5.00 | $1.25 | $0.10 |
| Sonnet 4.5 | $3.00 | $15.00 | $3.75 | $0.30 |
| Opus 4.5 | $5.00 | $25.00 | $6.25 | $0.50 |
| Opus 4.1 | $15.00 | $75.00 | $18.75 | $1.50 |
| Sonnet 4 | $3.00 | $15.00 | $3.75 | $0.30 |
| Opus 4 | $15.00 | $75.00 | $18.75 | $1.50 |
| Haiku 3 | $0.25 | $1.25 | $0.30 | $0.03 |

## MySQL Setup

The table is auto-created on first use. To create it manually:

```bash
mysql -h your-mysql-host -u your_user -p claude_tracker < src/claude_token_tracker/schema.sql
```

## License

MIT

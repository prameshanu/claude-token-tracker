# claude-token-tracker

Automatic token usage and cost tracking for the Anthropic Claude API. Drop-in replacement for the Anthropic SDK client that logs every API call to MySQL and/or Excel — with zero changes to your existing code.

## Features

- **Drop-in replacement** — swap one import, everything else stays the same
- **Automatic tracking** — intercepts `messages.create()` and `messages.stream()` transparently
- **MySQL logging** — persistent storage with connection pooling
- **Excel export** — real-time logging to `.xlsx` or on-demand export from MySQL
- **Cost calculation** — built-in pricing for all Claude models (configurable)
- **Sync + Async** — supports both `Anthropic` and `AsyncAnthropic` clients
- **Non-blocking** — DB/Excel writes happen in background threads by default
- **Never breaks your app** — all tracking is wrapped in try/except

## Installation

```bash
pip install claude-token-tracker
```

Or install from source:

```bash
git clone https://github.com/prameshanu/claude-token-tracker.git
cd claude-token-tracker
pip install -e .
```

## Quick Start

### 1. Set environment variables

```bash
export CLAUDE_TRACKER_MYSQL_HOST=10.8.0.6
export CLAUDE_TRACKER_MYSQL_USER=your_user
export CLAUDE_TRACKER_MYSQL_PASSWORD=your_password
export CLAUDE_TRACKER_MYSQL_DATABASE=claude_tracker
```

### 2. Swap the import

```python
# Before
import anthropic
client = anthropic.AsyncAnthropic(api_key="sk-...")

# After
from claude_token_tracker import TrackedAsyncAnthropic
client = TrackedAsyncAnthropic(api_key="sk-...", project="my_app", task_label="generate")
```

That's it. All your existing `client.messages.create(...)` and `async with client.messages.stream(...)` calls work unchanged.

### 3. Query your usage

```sql
SELECT model,
       SUM(input_tokens) AS total_input,
       SUM(output_tokens) AS total_output,
       SUM(input_cost + output_cost) AS total_cost
FROM claude_token_usage
GROUP BY model;
```

## Excel Support

### Real-time logging to Excel (alongside MySQL)

```bash
export CLAUDE_TRACKER_EXCEL_ENABLED=true
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
| `CLAUDE_TRACKER_MYSQL_HOST` | `10.8.0.6` | MySQL server host |
| `CLAUDE_TRACKER_MYSQL_PORT` | `3306` | MySQL server port |
| `CLAUDE_TRACKER_MYSQL_USER` | `""` | MySQL username |
| `CLAUDE_TRACKER_MYSQL_PASSWORD` | `""` | MySQL password |
| `CLAUDE_TRACKER_MYSQL_DATABASE` | `claude_tracker` | MySQL database name |
| `CLAUDE_TRACKER_DEFAULT_PROJECT` | `""` | Default project label for all logs |
| `CLAUDE_TRACKER_DEFAULT_TASK_LABEL` | `""` | Default task label for all logs |
| `CLAUDE_TRACKER_EXCEL_ENABLED` | `false` | Enable real-time Excel logging |
| `CLAUDE_TRACKER_EXCEL_PATH` | `claude_token_usage.xlsx` | Path to Excel file |
| `CLAUDE_TRACKER_AUTO_CREATE_TABLE` | `true` | Auto-create MySQL table on first use |
| `CLAUDE_TRACKER_POOL_SIZE` | `5` | MySQL connection pool size |

### Programmatic configuration

```python
from claude_token_tracker import TrackedAsyncAnthropic, TrackerConfig

config = TrackerConfig(
    mysql_host="10.8.0.6",
    mysql_user="tracker",
    mysql_password="secret",
    mysql_database="claude_tracker",
    excel_enabled=True,
    excel_path="usage.xlsx",
)

client = TrackedAsyncAnthropic(
    api_key="sk-...",
    tracker_config=config,
    project="my_app",
    task_label="summarize",
)
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
| `input_cost` | Input cost in USD |
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

## Supported Models & Pricing

Built-in pricing (USD per million tokens):

| Model | Input | Output |
|---|---|---|
| claude-opus-4-20250514 | $15.00 | $75.00 |
| claude-sonnet-4-20250514 | $3.00 | $15.00 |
| claude-haiku-4-20250414 | $0.80 | $4.00 |
| claude-haiku-4-5-20251001 | $1.00 | $5.00 |
| claude-3-5-sonnet-20241022 | $3.00 | $15.00 |
| claude-3-5-haiku-20241022 | $0.80 | $4.00 |
| claude-3-opus-20240229 | $15.00 | $75.00 |

Custom pricing overrides:

```python
config = TrackerConfig(
    pricing_overrides={
        "my-custom-model": {"input_per_mtok": 2.00, "output_per_mtok": 10.00}
    }
)
```

## MySQL Setup

The table is auto-created on first use. To create it manually:

```bash
mysql -h 10.8.0.6 -u your_user -p claude_tracker < src/claude_token_tracker/schema.sql
```

## License

MIT

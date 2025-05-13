# Insightful-automations

This tool extracts employee app and website usage data from the Insightful API, processing data by project with optimized batch processing to respect API rate limits.

## Overview

The Insightful API Data Extractor allows you to:

- Extract app/website usage data for employees within specific projects
- Process data in optimized batches to balance speed with API rate limits
- Cache API responses to disk to avoid redundant API calls
- Export results to CSV for further analysis

## Available Projects

The following projects are available for data extraction:

| Project ID | Project Name |
|------------|--------------|
| wzx8dcze_04iuwk | Guppy |
| whosz5wuyuvbo2v | Delta |
| wlfrdwxfpd7ud61 | Heka |
| wknprrdwhywzdg- | Prism |

You can specify these projects either by name (`--project "Guppy"`) or by ID (`--project-id "wzx8dcze_04iuwk"`).


## Installation

1. Ensure you have Python 3.6+ installed
2. Install required dependencies:

```bash
pip install requests pandas click
```

3. Configure your API key in the script or use environment variables

## Command Line Interface

The script provides a comprehensive CLI with numerous options to customize the data extraction process.

### Basic Usage

```bash
python insightful_app.py --project "Project Name"
```

### All Available Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--project` | `-p` | string | - | Project name from the mapping (e.g., "Guppy", "Delta") |
| `--project-id` | `-pid` | string | - | Project ID directly (e.g., "wzx8dcze_04iuwk") |
| `--output` | `-o` | string | auto-generated | Output filename (default: insightful_<project>_apps_<dates>.csv) |
| `--list-projects` | `-l` | flag | False | List all available projects and exit |
| `--start-date` | `-sd` | string | - | Start date in YYYY-MM-DD format |
| `--end-date` | `-ed` | string | - | End date in YYYY-MM-DD format |
| `--days` | `-d` | integer | 7 | Number of days to look back if no dates specified |
| `--threads` | `-t` | integer | 5 | Number of parallel threads to use per batch |
| `--delay` | `-dl` | float | 0.5 | Delay between individual API requests in seconds |
| `--batch-size` | `-bs` | integer | 5 | Number of employees to process in each batch |
| `--batch-delay` | `-bd` | float | 1.0 | Delay between batches in seconds |
| `--use-cache` | - | flag | True | Use disk cache for API responses |
| `--no-cache` | - | flag | False | Disable disk caching of API responses |
| `--cache-file` | - | string | insightful_api_cache.json | Cache file location |
| `--verbose` | `-v` | flag | False | Enable verbose logging |

### Common Usage Examples

#### List available projects
```bash
python insightful_app.py --list-projects
```

#### Extract data for a specific project using project name
```bash
python insightful_app.py --project "Guppy"
```

#### Extract data for a specific project using project ID
```bash
python insightful_app.py --project-id "wzx8dcze_04iuwk"
```

#### Specify a custom date range
```bash
python insightful_app.py --project "Guppy" --start-date "2025-04-01" --end-date "2025-04-30"
```

#### Look back a specific number of days
```bash
python insightful_app.py --project "Guppy" --days 14
```

#### Optimize performance with batch settings
```bash
python insightful_app.py --project "Guppy" --batch-size 8 --batch-delay 1.5 --threads 5
```

#### Specify output file
```bash
python insightful_app.py --project "Guppy" --output "guppy_productivity_report.csv"
```

#### Run with verbose logging
```bash
python insightful_app.py --project "Guppy" --verbose
```

#### Disable caching
```bash
python insightful_app.py --project "Guppy" --no-cache
```

#### Fully optimized command
```bash
python insightful_app.py --project "Guppy" --days 14 --threads 5 --batch-size 8 --batch-delay 1.5 --delay 0.3 --use-cache --verbose
```

## Understanding Batch Processing

This script uses an optimized batch processing approach to balance throughput with API rate limiting:

1. **Batches**: Employees are processed in batches (default: 5 employees per batch)
2. **Parallel Processing**: Within each batch, API requests run in parallel threads
3. **Batch Delays**: A configurable delay occurs between batches (default: 1 second)
4. **Individual Delays**: A smaller delay between individual API requests (default: 0.5 seconds)

### Optimizing Performance

To optimize performance while respecting API rate limits:

- **For faster processing**: Increase batch size or reduce delays
- **If hitting rate limits**: Decrease batch size or increase delays
- **For maximum speed**: Increase thread count, but be cautious of API limits

A good starting point is:
```bash
--batch-size 8 --batch-delay 1.5 --delay 0.3 --threads 5
```

## Caching Mechanism

The script implements disk-based caching to reduce redundant API calls:

- Cache is stored in a JSON file (default: insightful_api_cache.json)
- Cached responses are keyed by employee, project, and date range
- Cache persists between script runs
- Use `--no-cache` to disable caching, or `--cache-file` to specify a custom location

## Output Format

The script outputs a CSV file with the following columns:

- `employee_id`: The employee's Insightful ID
- `name`: Employee's name
- `email`: Employee's email address
- `project_id`: The project ID
- `project_name`: The project name
- `apps`: JSON array of app/website names
- `usage`: JSON array of corresponding usage times

## Troubleshooting

### Rate Limiting Issues

If you encounter rate limiting errors:
1. Increase `--batch-delay` to add more time between batches
2. Decrease `--batch-size` to reduce parallel requests
3. Increase `--delay` for more time between individual requests

### Performance Issues

If the script is running too slowly:
1. Ensure `--use-cache` is enabled
2. Increase `--batch-size` to process more employees per batch
3. Decrease `--batch-delay` and `--delay` values
4. Increase `--threads` for more parallel processing

### No Data Found

If no data is found:
1. Check that the project name or ID is correct with `--list-projects`
2. Verify the date range is appropriate
3. Run with `--verbose` to see detailed logs
4. Check your API key has the correct permissions

# calendar_stats

Script for fetching total time for events from iCloud calendars via CalDAV
for a given date range.

Usage:

```
calendar_stats.py calendar_name [date_start] [date_end]
```

If no days provided it will fetch events for the current day.

Several calendars can be passed separated by a comma (e.g. `work,projects`).
Statistics shows total time across all calendars without per-calendar breakdown.

## Setup

Requirements: Apple ID with two-factor authentication enabled, an
[app-specific password](https://support.apple.com/en-us/102654), and the
`caldav` package:

```
pip install -r requirements.txt
```

Credentials can be passed via flags or environment variables
(`CALDAV_USERNAME`, `CALDAV_PASSWORD`):

```
CALDAV_USERNAME=me@icloud.com CALDAV_PASSWORD=xxxx-xxxx-xxxx-xxxx \
    ./calendar_stats.py work,projects w
```

The CalDAV server URL defaults to `https://caldav.icloud.com/` and can be
overridden with `--caldav-url`.

## Notes

All-day events count as 24 hours. Events crossing midnight are split and
counted separately for each day (in the system time zone). Recurring events
are expanded, and travel time (`X-APPLE-TRAVEL-DURATION`) is counted as time
before the event.

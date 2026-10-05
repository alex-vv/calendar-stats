# calendar_stats

Script for fetching total time for events from mac os calendar for a given date range

Usage:

```
calendar_stats.py calendar_name [date_start] [date_end]
```

If no days provided it will fetch events for the current day.

Several calendars can be passed separated by a comma (e.g. `work,projects`).
Statistics shows total time across all calendars without per-calendar breakdown.

## Methods

Events are fetched via AppleScript from the local Calendar.app by default.
As an alternative, CalDAV can be used (works without Calendar.app).

### CalDAV

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
    ./calendar_stats.py work,projects w --method caldav
```

The CalDAV server URL defaults to `https://caldav.icloud.com/` and can be
overridden with `--caldav-url`.

All-day events count as 24 hours.

#!/usr/bin/env python3
"""
Script for fetching events from the macOS calendar for a given date.
"""

import argparse
import os
import subprocess
import re
from datetime import datetime, timedelta


def parse_apple_date(date_str: str) -> str:
    """
    Converts a date from AppleScript format to dd.mm.yyyy hh:mm.

    Example input format: "Friday, 20 March 2026 at 17:30:00"
    """
    if not date_str:
        return ''

    # Extract date components using regex
    match = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4})\s+at\s+(\d{2}):(\d{2}):(\d{2})', date_str)
    if not match:
        return date_str

    day, month_name, year, hour, minute, _ = match.groups()

    months = {
        'January': '01', 'February': '02', 'March': '03', 'April': '04',
        'May': '05', 'June': '06', 'July': '07', 'August': '08',
        'September': '09', 'October': '10', 'November': '11', 'December': '12'
    }

    month = months.get(month_name, '01')
    return f"{day.zfill(2)}.{month}.{year} {hour}:{minute}"


def parse_apple_date_to_datetime(date_str: str) -> datetime | None:
    """
    Converts a date from AppleScript format to a datetime object.
    """
    if not date_str:
        return None

    match = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4})\s+at\s+(\d{2}):(\d{2}):(\d{2})', date_str)
    if not match:
        return None

    day, month_name, year, hour, minute, second = match.groups()

    months = {
        'January': 1, 'February': 2, 'March': 3, 'April': 4,
        'May': 5, 'June': 6, 'July': 7, 'August': 8,
        'September': 9, 'October': 10, 'November': 11, 'December': 12
    }

    month = months.get(month_name, 1)
    return datetime(int(year), month, int(day), int(hour), int(minute), int(second))


def calculate_duration_hours(start_dt: datetime | None, end_dt: datetime | None) -> float:
    """
    Calculates the event duration in hours (rounded to two decimals).
    """
    if not start_dt or not end_dt:
        return 0.0

    duration = (end_dt - start_dt).total_seconds() / 3600
    return round(duration, 2)


def get_calendar_events(calendar_name: str, date_start: str, date_end: str) -> list[dict]:
    """
    Fetches events from the specified macOS calendar for the given period.

    Args:
        calendar_name: Calendar name
        date_start: Start date in YYYY-MM-DD format
        date_end: End date in YYYY-MM-DD format

    Returns:
        List of dictionaries with event information
    """
    # Convert YYYY-MM-DD to a format AppleScript understands: "20 March 2026"
    months = {
        1: 'January', 2: 'February', 3: 'March', 4: 'April',
        5: 'May', 6: 'June', 7: 'July', 8: 'August',
        9: 'September', 10: 'October', 11: 'November', 12: 'December'
    }

    dt_start = datetime.strptime(date_start, '%Y-%m-%d')
    dt_end = datetime.strptime(date_end, '%Y-%m-%d')

    apple_start = f"{dt_start.day} {months[dt_start.month]} {dt_start.year}"
    apple_end = f"{dt_end.day} {months[dt_end.month]} {dt_end.year}"

    apple_script = f'''
tell application "Calendar"
    set calendarList to name of every calendar
    
    if "{calendar_name}" is not in calendarList then
        error "Calendar '{calendar_name}' not found"
    end if
    
    set targetCalendar to calendar "{calendar_name}"

    set startDate to date "{apple_start}"
    set startDate to startDate - (time of startDate)
    set endDate to date "{apple_end}"
    set endDate to endDate - (time of endDate) + (1 * days)

    set dayEvents to every event of targetCalendar whose start date >= startDate and start date < endDate

    set outputText to ""
    repeat with evt in dayEvents
        set summaryText to summary of evt
        set startDateText to start date of evt
        set endDateText to end date of evt
        set locationText to location of evt
        if outputText is not "" then
            set outputText to outputText & linefeed
        end if
        set outputText to outputText & (summaryText & "|" & startDateText & "|" & endDateText & "|" & locationText)
    end repeat
    return outputText
end tell
'''

    try:
        result = subprocess.run(
            ['osascript', '-e', apple_script],
            capture_output=True,
            text=True,
            check=True
        )

        output = result.stdout.strip()
        if not output:
            return []

        events = []
        for line in output.split('\n'):
            parts = line.split('|')
            if len(parts) >= 3:
                event = {
                    'summary': parts[0] if parts[0] else 'Untitled',
                    'start': parse_apple_date_to_datetime(parts[1] if len(parts) > 1 else ''),
                    'end': parse_apple_date_to_datetime(parts[2] if len(parts) > 2 else ''),
                    'location': parts[3] if len(parts) > 3 and parts[3] != 'missing value' else None
                }
                events.append(event)

        return events

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip()
        if "not found" in error_msg:
            print(f"Error: Calendar '{calendar_name}' not found")
        else:
            print(f"Error: {error_msg}")
        return []
    except Exception as e:
        print(f"Error: {e}")
        return []


def _ical_to_datetime(value):
    """
    Converts an icalendar DTSTART/DTEND value to a naive local datetime.
    """
    if value is None:
        return None

    dt = value.dt
    if isinstance(dt, datetime):
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt

    # All-day event: date has no time component
    return datetime.combine(dt, datetime.min.time())


def get_calendar_events_caldav(
    username: str,
    password: str,
    calendar_names: list[str],
    date_start: str,
    date_end: str,
    url: str = 'https://caldav.icloud.com/',
) -> list[dict]:
    """
    Fetches events from calendars via CalDAV for the given period.

    Args:
        username: Apple ID (email)
        password: App-specific password
        calendar_names: Calendar display names
        date_start: Start date in YYYY-MM-DD format
        date_end: End date in YYYY-MM-DD format
        url: CalDAV server URL

    Returns:
        List of dictionaries with event information
    """
    try:
        import caldav
    except ImportError:
        print("Error: 'caldav' package is required for --method caldav. "
              "Install it with: pip install -r requirements.txt")
        return []

    local_tz = datetime.now().astimezone().tzinfo
    search_start = datetime.strptime(date_start, '%Y-%m-%d').replace(tzinfo=local_tz)
    search_end = datetime.strptime(date_end, '%Y-%m-%d').replace(tzinfo=local_tz) + timedelta(days=1)

    try:
        client = caldav.DAVClient(url=url, username=username, password=password)
        principal = client.principal()
        calendars = principal.calendars()
    except Exception as e:
        print(f"Error: CalDAV connection failed: {e}")
        return []

    events = []
    for calendar_name in calendar_names:
        matching = [c for c in calendars if c.get_display_name() == calendar_name]
        if not matching:
            print(f"Warning: Calendar '{calendar_name}' not found via CalDAV")
            continue

        for calendar in matching:
            try:
                results = calendar.search(
                    start=search_start,
                    end=search_end,
                    event=True,
                    expand=True,
                )
            except Exception as e:
                print(f"Error: Failed to fetch '{calendar_name}': {e}")
                continue

            for item in results:
                comp = getattr(item, 'icalendar_component', None)
                if comp is None:
                    comp = item.vobject_instance.vevent

                dtstart_value = comp.get('DTSTART')
                dtend_value = comp.get('DTEND')
                start_dt = _ical_to_datetime(dtstart_value)
                end_dt = _ical_to_datetime(dtend_value)

                # All-day event without DTEND spans a full day
                if (end_dt is None and start_dt is not None
                        and dtstart_value is not None
                        and not isinstance(dtstart_value.dt, datetime)):
                    end_dt = start_dt + timedelta(days=1)

                # Fallback to DURATION when DTEND is missing
                if end_dt is None and start_dt is not None and comp.get('DURATION') is not None:
                    end_dt = start_dt + comp.get('DURATION').dt

                summary = comp.get('SUMMARY')
                location = comp.get('LOCATION')
                events.append({
                    'summary': str(summary) if summary else 'Untitled',
                    'start': start_dt,
                    'end': end_dt,
                    'location': str(location) if location else None,
                })

    return events


def main():
    parser = argparse.ArgumentParser(
        description='Fetch events from the macOS calendar for a given period'
    )
    parser.add_argument(
        'calendar',
        help='Calendar name, or several names separated by "," (e.g. work,projects)'
    )
    parser.add_argument(
        'date_start',
        nargs='?',
        default=None,
        help='Start date in YYYY-MM-DD format, or a week range: "w"/"w0" '
             '(current week), "wN" (N weeks ahead), "w-N" (N weeks back). '
             'Defaults to today'
    )
    parser.add_argument(
        'date_end',
        nargs='?',
        default=None,
        help='End date in YYYY-MM-DD format (defaults to today)'
    )
    parser.add_argument(
        '--prefix',
        default=None,
        help='Filter events by title prefix'
    )
    parser.add_argument(
        '--method',
        choices=['applescript', 'caldav'],
        default='applescript',
        help='How to fetch events (default: applescript)'
    )
    parser.add_argument(
        '--username',
        default=None,
        help='Apple ID for CalDAV (or CALDAV_USERNAME env var)'
    )
    parser.add_argument(
        '--password',
        default=None,
        help='App-specific password for CalDAV (or CALDAV_PASSWORD env var)'
    )
    parser.add_argument(
        '--caldav-url',
        default='https://caldav.icloud.com/',
        help='CalDAV server URL (default: https://caldav.icloud.com/)'
    )

    args = parser.parse_args()

    today = datetime.now()

    date_start = args.date_start if args.date_start else today.strftime('%Y-%m-%d')
    date_end = args.date_end if args.date_end else date_start

    # Week range: "w" / "w0" = current week, "wN" = N weeks ahead, "w-N" = N weeks back
    week_match = re.fullmatch(r'w(-?\d+)?', date_start)
    if week_match:
        week_offset = int(week_match.group(1)) if week_match.group(1) else 0
        monday = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
        date_end = (monday + timedelta(days=6)).strftime('%Y-%m-%d')
        date_start = monday.strftime('%Y-%m-%d')

    # Validate dates
    for date_str, arg_name in [(date_start, 'date_start'), (date_end, 'date_end')]:
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            print(f"Error: Invalid {arg_name} date format. Use YYYY-MM-DD")
            return

    calendars = [c.strip() for c in args.calendar.split(',') if c.strip()]

    print(f"Calendar: {', '.join(calendars)}")
    print(f"Period: {date_start} — {date_end}")
    print()

    if args.method == 'caldav':
        username = args.username or os.environ.get('CALDAV_USERNAME')
        password = args.password or os.environ.get('CALDAV_PASSWORD')
        if not username or not password:
            print("Error: CalDAV requires --username/--password "
                  "or CALDAV_USERNAME/CALDAV_PASSWORD env vars")
            return
        events = get_calendar_events_caldav(
            username, password, calendars, date_start, date_end, args.caldav_url
        )
    else:
        events = []
        for calendar in calendars:
            events.extend(get_calendar_events(calendar, date_start, date_end))

    # Filter by prefix
    if args.prefix:
        events = [e for e in events if e.get('summary', '').startswith(args.prefix)]

    if not events:
        print("No events found")
        return

    grouped = {}
    for event in events:
        start_dt = event.get('start')
        day_key = start_dt.strftime('%Y-%m-%d') if start_dt else 'No date'
        grouped.setdefault(day_key, []).append(event)

    total_duration = 0.0
    for day_key in sorted(grouped.keys()):
        day_duration = 0.0
        for event in grouped[day_key]:
            day_duration += calculate_duration_hours(
                event.get('start'), event.get('end')
            )
        total_duration += day_duration
        print(f"{day_key}: {day_duration:.2f} h")

    print(f"\nTotal: {total_duration:.2f} h")


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Script for fetching events from iCloud calendars via CalDAV for a given date.
"""

import argparse
import os
import re
from datetime import datetime, timedelta


def split_event_hours(start_dt: datetime | None, end_dt: datetime | None) -> dict[str, float]:
    """
    Splits an event duration across calendar days.

    Events crossing midnight are counted separately for each day.
    Returns a mapping of 'YYYY-MM-DD' to hours spent on that day.
    """
    result: dict[str, float] = {}
    if not start_dt or not end_dt or end_dt <= start_dt:
        return result

    day = start_dt.date()
    last_day = end_dt.date()
    while day <= last_day:
        day_start = datetime.combine(day, datetime.min.time())
        day_end = day_start + timedelta(days=1)
        overlap_start = max(start_dt, day_start)
        overlap_end = min(end_dt, day_end)
        hours = (overlap_end - overlap_start).total_seconds() / 3600
        if hours > 0:
            result[day.strftime('%Y-%m-%d')] = hours
        day += timedelta(days=1)

    return result


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


def _travel_delta(comp):
    """
    Extracts the Apple travel time (X-APPLE-TRAVEL-DURATION) as a timedelta.
    """
    value = comp.get('X-APPLE-TRAVEL-DURATION')
    if value is None:
        return None

    dt = getattr(value, 'dt', value)
    if isinstance(dt, timedelta):
        return dt

    if isinstance(dt, str):
        try:
            from icalendar.prop import vDuration
            return vDuration.from_ical(dt)
        except Exception:
            return None

    return None


def get_calendar_events(
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
        print("Error: 'caldav' package is required. "
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

                # Travel time counts as time before the event
                travel = _travel_delta(comp)
                if travel and start_dt is not None:
                    start_dt = start_dt - travel

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
        description='Fetch events from iCloud calendars via CalDAV for a given period'
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

    username = args.username or os.environ.get('CALDAV_USERNAME')
    password = args.password or os.environ.get('CALDAV_PASSWORD')
    if not username or not password:
        print("Error: CalDAV requires --username/--password "
              "or CALDAV_USERNAME/CALDAV_PASSWORD env vars")
        return

    events = get_calendar_events(
        username, password, calendars, date_start, date_end, args.caldav_url
    )

    # Filter by prefix
    if args.prefix:
        events = [e for e in events if e.get('summary', '').startswith(args.prefix)]

    if not events:
        print("No events found")
        return

    day_totals = {}
    for event in events:
        start_dt = event.get('start')
        if not start_dt:
            day_totals.setdefault('No date', 0.0)
            continue
        day_totals.setdefault(start_dt.strftime('%Y-%m-%d'), 0.0)
        for day_key, hours in split_event_hours(start_dt, event.get('end')).items():
            day_totals[day_key] = day_totals.get(day_key, 0.0) + hours

    total_duration = 0.0
    for day_key in sorted(day_totals.keys()):
        day_duration = round(day_totals[day_key], 2)
        total_duration += day_duration
        print(f"{day_key}: {day_duration:.2f} h")

    print(f"\nTotal: {total_duration:.2f} h")


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Script for fetching events from the macOS calendar for a given date.
"""

import argparse
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


def calculate_duration_hours(start_str: str, end_str: str) -> float:
    """
    Calculates the event duration in hours (rounded to two decimals).
    """
    start_dt = parse_apple_date_to_datetime(start_str)
    end_dt = parse_apple_date_to_datetime(end_str)

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
                    'startDate': parts[1] if len(parts) > 1 else '',
                    'endDate': parts[2] if len(parts) > 2 else '',
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


def main():
    parser = argparse.ArgumentParser(
        description='Fetch events from the macOS calendar for a given period'
    )
    parser.add_argument(
        'calendar',
        help='Calendar name'
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

    print(f"Calendar: {args.calendar}")
    print(f"Period: {date_start} — {date_end}")
    print()

    events = get_calendar_events(args.calendar, date_start, date_end)

    # Filter by prefix
    if args.prefix:
        events = [e for e in events if e.get('summary', '').startswith(args.prefix)]

    if not events:
        print("No events found")
        return

    grouped = {}
    for event in events:
        start_dt = parse_apple_date_to_datetime(event.get('startDate', ''))
        day_key = start_dt.strftime('%Y-%m-%d') if start_dt else 'No date'
        grouped.setdefault(day_key, []).append(event)

    total_duration = 0.0
    for day_key in sorted(grouped.keys()):
        day_duration = 0.0
        for event in grouped[day_key]:
            day_duration += calculate_duration_hours(
                event.get('startDate', ''), event.get('endDate', '')
            )
        total_duration += day_duration
        print(f"{day_key}: {day_duration:.2f} h")

    print(f"\nTotal: {total_duration:.2f} h")


if __name__ == '__main__':
    main()

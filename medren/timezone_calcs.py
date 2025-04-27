from timezonefinder import TimezoneFinder
from datetime import datetime
from zoneinfo import ZoneInfo


def get_timezone_offset(lat: float, lon: float, date: datetime):
    """
    Get timezone offset (in hours) for given latitude, longitude and date.

    Args:
        lat (float): Latitude
        lon (float): Longitude
        date (datetime.date or datetime.datetime): Date to check (with or without time)

    Returns:
        float: Offset from UTC in hours (including DST if applicable)
    """
    tf = TimezoneFinder()
    timezone_name = tf.timezone_at(lng=lon, lat=lat)
    if timezone_name is None:
        raise ValueError("Could not determine timezone for given coordinates.")

    if not isinstance(date, datetime):
        # If date is a date, convert to datetime at midnight
        date = datetime.combine(date, datetime.min.time())

    tz = ZoneInfo(timezone_name)
    localized_dt = date.astimezone(tz)
    offset_seconds = localized_dt.utcoffset().total_seconds()
    offset_hours = offset_seconds / 3600
    return offset_hours


def test_timezeone_offset():
    tlv_lat_lng = 32.08, 34.78
    winter_date = datetime(2025, 1, 1)
    offset = get_timezone_offset(*tlv_lat_lng, date=winter_date)
    assert offset == 2

    summer_date = datetime(2025, 8, 1)
    offset = get_timezone_offset(*tlv_lat_lng, date=summer_date)
    assert offset == 3

# Example usage:
if __name__ == "__main__":
    lat = 40.7128
    lon = -74.0060
    date = datetime(2025, 6, 15)
    offset = get_timezone_offset(lat, lon, date)
    print(f"Timezone offset: {offset} hours")

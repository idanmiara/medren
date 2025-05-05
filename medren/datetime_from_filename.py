import re
from datetime import datetime

def extract_datetime_from_filename(filename):
    patterns = [
        # IMG_20240501_203015.jpg or VID_20240501_203015.mp4 or PXL_20240501_203015.mp4
        r'(?P<date>\d{8})[_-](?P<time>\d{6})',

        # Screenshot_20240501-203015.png
        r'(?P<date>\d{8})-(?P<time>\d{6})',

        # 2024-05-01 20.30.15.jpg
        r'(?P<date>\d{4}-\d{2}-\d{2})[ _](?P<time>\d{2}\.\d{2}\.\d{2})',

        # DSC20240501.jpg (date only)
        # r'DSC(?P<date>\d{8})',

        # Simple date: 20240501.jpg
        # r'^(?P<date>\d{8})$'
    ]

    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            try:
                date_str = match.group('date')
                time_str = match.group('time') if 'time' in match.groupdict() else '000000'

                # Normalize separators
                date_str = date_str.replace('-', '')
                time_str = time_str.replace('.', '')

                dt = datetime.strptime(date_str + time_str, '%Y%m%d%H%M%S')
                return dt
            except ValueError:
                continue
    return None

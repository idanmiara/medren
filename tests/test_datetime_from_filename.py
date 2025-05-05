import pytest
from datetime import datetime

from medren.datetime_from_filename import extract_datetime_from_filename


@pytest.mark.parametrize("filename, expected", [
    ("IMG_20240501_203015.jpg", datetime(2024, 5, 1, 20, 30, 15)),
    ("IMG_20240501_203015(1).jpg", datetime(2024, 5, 1, 20, 30, 15)),
    ("IMG_20240501_203015_2.jpg", datetime(2024, 5, 1, 20, 30, 15)),
    ("VID_20240501_203015.mp4", datetime(2024, 5, 1, 20, 30, 15)),
    ("PXL_20240501_203015.mp4", datetime(2024, 5, 1, 20, 30, 15)),
    ("Screenshot_20240501-203015.png", datetime(2024, 5, 1, 20, 30, 15)),
    ("2024-05-01 20.30.15.jpg", datetime(2024, 5, 1, 20, 30, 15)),
])
def test_extract_datetime_valid_patterns(filename, expected):
    assert extract_datetime_from_filename(filename) == expected

@pytest.mark.parametrize("filename", [
    "randomfilename.jpg",
    "photo.jpg",
    "IMG_no_datetime.jpg",
    "",
    "202405.jpg",
    "IMG_20241301_203015.jpg",  # Invalid month
    "IMG_20240532_203015.jpg",  # Invalid day
    "2024-05-01 25.30.15.jpg",  # Invalid hour
    "DSC20240501.jpg",
    "20240501.jpg",
])
def test_extract_datetime_invalid_patterns(filename):
    assert extract_datetime_from_filename(filename) is None

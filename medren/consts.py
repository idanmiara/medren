DEFAULT_PROFILE_NAME = 'default'
DEFAULT_SEPARATOR = '_'
DEFAULT_TEMPLATE = '{datetime}{s}{make}{s}{model}{s}{cname}{s}{suffix}{ext}'
DEFAULT_DATETIME_FORMAT = '%Y-%m-%d-%H-%M-%S'

# Generic filename patterns
DAY_PATTERN = r'0[1-9]|[12]\d|3[01]'
MONTH_PATTERN = r'0[1-9]|1[0-2]'
HOUR_PATTERN = r'[01]\d|2[0-3]'
MINUTE_PATTERN = r'[0-5]\d'
SECOND_PATTERN = r'[0-5]\d'
SEP = r'[-_ ]?'
YEAR_PATTERN = r'\d{4}'

GENERIC_PATTERNS: list[str] = [
    r'^IMG[_-]?\d+',
    r'^DSC[_-]?\d+',
    r'^VID[_-]?\d+',
    r'^MOV[_-]?\d+',
    r'^PXL[_-]?\d+',
    r'^Screenshot[_-]?\d+',
    r'^Photo[_-]?\d+',
    f'^{YEAR_PATTERN}{SEP}({DAY_PATTERN}){SEP}({DAY_PATTERN}){SEP}({HOUR_PATTERN}){SEP}({MINUTE_PATTERN})({SEP}{SECOND_PATTERN})?',
]

from dataclasses import dataclass
from dataclasses import dataclass
from enum import Enum, IntEnum, auto, StrEnum

from medren.consts import DEFAULT_TEMPLATE, DEFAULT_DATETIME_FORMAT, DEFAULT_PROFILE_NAME


class Separator(Enum):
    separator = auto()
    separator_index = auto()
    separator_prefix = auto()
    separator_exif = auto()
    separator_name = auto()
    separator_datetime = auto()


sep_abbr: dict[str, Separator] = {
    's': Separator.separator,
    'si': Separator.separator_index,
    'sp': Separator.separator_prefix,
    'se': Separator.separator_exif,
    'sn': Separator.separator_name,
    'sd': Separator.separator_datetime,
}
assert set(sep_abbr.values()) == set(s for s in Separator)


class Modes(StrEnum):
    file = "file"
    dir = "dir"
    recursive = "recursive"


@dataclass
class Profile:
    template: str = DEFAULT_TEMPLATE,
    datetime_format: str = DEFAULT_DATETIME_FORMAT,
    mode: Modes = Modes.dir
    normalize: bool = False
    prefix: str = ''
    suffix: str = ''
    org_full_path: str = ''
    separators: dict[str, str] | None = None

    @classmethod
    def expand_separators(cls, values):
        s = values.pop('separators')
        if s:
            values.update(s)

    def get_vars(self):
        values = vars(self)
        self.expand_separators(values)
        return values


profiles: dict[str, Profile] = {
    DEFAULT_PROFILE_NAME: Profile(),
    "enumerated": Profile(
        template='{prefix}{s}#{idx:03d}{si}{datetime}{s}{cname}{sn}{suffix}{ext}',
    ),
    "compact": Profile(
        template='{prefix}{sc}{datetime}{sd}{suffix}{ext}',
    ),
    "full": Profile(
        template='{prefix}{sc}{datetime}{sd}{cname}{sn}{make}{suffix}{ext}',
    ),
    "hashed": Profile(
        template='{prefix}{sc}{datetime}{sd}{cname}{sn}{make}{s}{sha256}{suffix}{ext}',
    ),
    "victor": Profile(
        template='{prefix}{sc}{datetime}{sd}{cname}{sn}{suffix}{ext}',
    ),
}

profile_keys = [k for k in Profile.__annotations__]

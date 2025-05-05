from dataclasses import dataclass
from enum import StrEnum

from medren.consts import DEFAULT_TEMPLATE, DEFAULT_DATETIME_FORMAT, DEFAULT_PROFILE_NAME


class Modes(StrEnum):
    file = "file"
    dir = "dir"
    recursive = "recursive"


@dataclass
class Profile:
    template: str = DEFAULT_TEMPLATE
    datetime_format: str = DEFAULT_DATETIME_FORMAT
    mode: Modes = Modes.dir
    normalize: bool = False
    prefix: str = ''
    suffix: str = ''
    org_full_path: str = ''
    separator: str = None

    def get_vars(self):
        values = vars(self)
        return values


profiles: dict[str, Profile] = {
    DEFAULT_PROFILE_NAME: Profile(),
    "enumerated": Profile(
        template='{prefix}{s}#{idx:03d}{s}{datetime}{s}{cname}{s}{suffix}{ext}',
    ),
    "geo": Profile(
        template='{prefix}{s}{datetime}{s}{pluscode}{s}{address}{s}{lat:.4f}{s}{lon:.4f}{ext}', # .4 digits ~ 11m accuracy
    ),
    "compact": Profile(
        template='{prefix}{s}{datetime}{s}{suffix}{ext}',
    ),
    "full": Profile(
        template='{prefix}{s}{datetime}{s}{cname}{s}{make}{s}{model}{s}{suffix}{ext}',
    ),
    "hashed": Profile(
        template='{prefix}{s}{datetime}{s}{make}{s}{model}{s}{sha256}{s}{suffix}{ext}',
    ),
    "victor": Profile(
        template='{prefix}{s}{datetime}{s}{make}{s}{model}{s}{name}{s}{suffix}{ext}',
    ),
}

profile_keys = [k for k in Profile.__annotations__]

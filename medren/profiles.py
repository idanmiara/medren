import dataclasses
from dataclasses import dataclass
from enum import Enum, IntEnum, auto

from medren.consts import DEFAULT_SEPERATOR, DEFAULT_TEMPLATE, DEFAULT_DATETIME_FORMAT, DEFAULT_PROFILE_NAME


def key_to_gui_key(key: str) -> str:
    return f"-{key.upper().replace('_', '-')}-"


class Separators(Enum):
    seperator = auto()
    seperator_index = auto()
    seperator_prefix = auto()
    seperator_make = auto()
    seperator_name = auto()
    seperator_datetime = auto()

    def gui_key(self) -> str:
        return key_to_gui_key(self.name)


sep_abbr: dict[str, Separators] = {
    's': Separators.seperator,
    'si': Separators.seperator_index,
    'sp': Separators.seperator_prefix,
    'sc': Separators.seperator_make,
    'sn': Separators.seperator_name,
    'sd': Separators.seperator_datetime,
}

class Modes(IntEnum):
    file = 0
    dir = 1
    recursive = 2

@dataclass
class Profile:
    template: str = DEFAULT_TEMPLATE,
    datetime_format: str = DEFAULT_DATETIME_FORMAT,
    mode: Modes = Modes.dir
    normalize: bool = False
    prefix: str = ''
    suffix: str = ''
    org_full_path: str = ''
    seperators: dict[str, str] | None = None
    # seperator: str = DEFAULT_SEPERATOR
    # seperator_make: str = DEFAULT_SEPERATOR
    # seperator_name: str = DEFAULT_SEPERATOR
    # seperator_datetime: str = DEFAULT_SEPERATOR


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

# profile_keys_old = [
#     '-PREFIX-', '-TEMPLATE-', '-DATETIME-FORMAT-', '-SUFFIX-', '-MODE-', '-NORMALIZE-', '-ORG-FULL-PATH-',
#     '-SEPERATOR-PREFIX-', '-SEPERATOR-INDEX-', '-SEPERATOR-NAME-', '-SEPERATOR-DATETIME-'
# ]
# profile_keys_old.sort()
profile_keys = [key_to_gui_key(k) for k in Profile.__annotations__]
# profile_keys.sort()
# assert profile_keys == profile_keys_old, f'{profile_keys=}, {profile_keys_old=}'


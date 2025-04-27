import csv
import glob
import hashlib
import logging
import math
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from geopy import Nominatim
from openlocationcode.openlocationcode import encode

from medren.backends import ExifClass, available_backends, backend_support
from medren.consts import DEFAULT_DATETIME_FORMAT, DEFAULT_TEMPLATE, DEFAULT_SEPARATOR, GENERIC_PATTERNS, \
    extension_normalized
from medren.util import filename_safe

logger = logging.getLogger(__name__)

MEDREN_DIR = Path(os.path.join(os.path.expanduser('~'), 'medren'))
MEDREN_DIR.mkdir(parents=True, exist_ok=True)
PROFILES_DIR = MEDREN_DIR / 'profiles'
PROFILES_DIR.mkdir(parents=True, exist_ok=True)


def hash_file(filename: Path | str, digest='sha256'):
    with open(filename, 'rb', buffering=0) as f:
        return hashlib.file_digest(f, digest).hexdigest()


@dataclass
class Renamer:
    """A class to handle media file renaming based on metadata."""
    prefix: str = field(default='')  # The prefix to use for renamed files
    suffix: str = field(default='')  # The suffix to use for renamed files
    template: str = field(default=DEFAULT_TEMPLATE)  # The template to use for the new filename
    datetime_format: str = field(default=DEFAULT_DATETIME_FORMAT)  # The format to use for the datetime
    normalize: bool = field(default=True)  # Whether to normalize the filename
    separator: str = field(default=DEFAULT_SEPARATOR)  # The separator between parts of the name
    backends: list[str] | None = None  # The backends to use for metadata extraction
    recursive: bool = field(default=False)  # Whether to recursively search for files
    do_calc_hash: bool | None = None
    do_calc_loc: bool | None = None
    do_calc_pluscode: bool | None = None
    geolocator: Nominatim | None = None

    def __post_init__(self):
        """Initialize backends after instance creation."""
        self.prefix = self.prefix or ''
        self.backends = self.backends or available_backends
        self.do_calc_hash = '{sha256}' in self.template
        self.do_calc_loc = '{address}' in self.template
        self.do_calc_pluscode = '{pluscode}' in self.template
        if self.do_calc_loc:
            self.geolocator = Nominatim(user_agent="medren")

    def is_generic(self, filename: str) -> bool:
        """
        Check if a filename matches generic patterns.

        Args:
            filename: The filename to check

        Returns:
            bool: True if the filename matches generic patterns
        """
        basename = os.path.splitext(filename)[0]
        return any(re.match(p, basename, re.I) for p in GENERIC_PATTERNS)

    def get_clean_name(self, basename: str) -> str:
        """
        Generate a suffix for the filename.

        Args:
            basename: The original basename

        Returns:
            str: The basename to append to the new filename
        """
        name = '' if self.is_generic(basename) else basename
        if name and self.normalize:
            name = re.sub(r'\\s+', '_', name)
        return name

    def fetch_meta(self, path: Path | str) -> ExifClass | None:
        """
        Extract datetime from file metadata.

        Args:
            path: Path to the file

        Returns:
            datetime.datetime | None: The extracted datetime or None if not found
        """
        ext = os.path.splitext(path)[1].lower()
        ext = extension_normalized.get(ext, ext)
        path = str(path)
        for backend in self.backends:
            supported_exts = backend_support[backend].ext
            if supported_exts is None or ext in supported_exts:
                try:
                    ex = backend_support[backend].func(path, logger)
                    if ex:
                        return ex
                except Exception as e:
                    logger.debug(f"Could not extract datetime from {path}: {e} using {backend}")
        logger.warning(f"No datetime found for {path}")
        return None

    def resolve_names(self, inputs: list[Path | str]) -> list[Path]:
        """
        Resolve names from inputs.

        Args:
            inputs: list of input paths
        """
        resolved_inputs = []
        for _path in inputs:
            path = Path(_path)
            if path.is_dir():
                if self.recursive:
                    path = path / '**/*'
                else:
                    path = path / '*'
            elif path.is_file():
                path = path.parent / path.name
            paths = list(glob.glob(str(path), recursive=True))
            resolved_inputs.extend(paths)
        resolved_inputs = [Path(p) for p in resolved_inputs]
        return resolved_inputs

    def generate_renames(self, inputs: list[Path | str],
                         resolve_names: bool = False) -> dict[str, tuple[Path, ExifClass]]:
        """
        Generate a preview of file renames.

        Args:
            inputs: Input files or dirs to process
            resolve_names: If true, the inputs would be resolved (wildcards, dirs)

        Returns:
            dict[str, tuple[Path, ExifClass]]: Dictionary mapping original
                filenames to new filenames and details
        """
        if resolve_names:
            inputs = self.resolve_names(inputs)
        renames, counter = {}, defaultdict(int)
        idx = 0
        dt_and_paths = []
        for path in inputs:
            if not path.is_file():
                continue
            ex = self.fetch_meta(path)
            if ex is not None:
                dt_and_paths.append((Path(path), ex))
                logger.debug(f"Fetched datetime {ex.dt} ({ex.goff=}) for {path} using {ex.backend}")
        dt_and_paths.sort(key=lambda x: x[1].dt)

        s = self.separator

        none_value = math.nan
        none_value_s = str(none_value)

        for path, ex in dt_and_paths:
            try:
                name = path.stem
                clean_name = self.get_clean_name(name)
                suffix = self.suffix
                ext = path.suffix
                datetime_str = ex.dt.strftime(self.datetime_format)
                exif_kwargs = ex.get_exif_kwargs(none_value=none_value)
                sha256 = hash_file(path) if self.do_calc_hash else ''
                address = None
                pluscode = None
                if self.do_calc_loc and ex.lat and ex.lon:
                    location = self.geolocator.reverse(f"{ex.lat}, {ex.lon}")
                    if location and location.address:
                        address = location.address
                    pluscode = encode(ex.lat, ex.lon)
                # Format the new filename using the template
                new_name = self.template.format(
                    prefix=self.prefix or none_value,
                    datetime=datetime_str or none_value,
                    name=name or none_value,
                    cname=clean_name or none_value,
                    suffix=suffix or none_value,
                    idx=idx,
                    sha256=sha256,
                    pluscode=pluscode or none_value,
                    address=address or none_value,
                    s=s,
                    ext=ext,
                    **exif_kwargs,
                )
                new_name = Path(new_name)

                # Remove trailing separators from the new filename
                new_stem, ext = os.path.splitext(new_name)
                new_stem = new_stem.replace(none_value_s+s,'').replace(s+none_value_s,'').replace(none_value_s,'')
                new_stem = filename_safe(new_stem)
                # if s and new_stem.endswith(s):
                #     new_stem = new_stem[:-len(s)]
                # if s and new_stem.startswith(s):
                #     new_stem = new_stem[len(s):]

                cnt = counter[new_name]
                if cnt > 0:
                    # Insert counter before the extension
                    new_stem = f"{clean_name}-{cnt}"
                new_name = new_stem + new_name.suffix

                counter[new_name] += 1
                renames[path] = (new_name, ex)
                idx += 1
            except Exception as e:
                logger.error(f"Error generating preview for {path}: {e}")
        return renames

    def apply_rename(self, renames: dict[str, tuple[Path, ExifClass]], logfile: Path | str | None = None) -> None:
        """
        Apply the renaming operations.

        Args:
            renames: Dictionary mapping original filenames to new filenames
        """
        try:
            f = writer = None
            if logfile:
                logfile = Path(logfile)
                logfile.parent.mkdir(parents=True, exist_ok=True)
                f = open(logfile, 'w', newline='', encoding='utf-8')
                writer = csv.writer(f)
                writer.writerow(['Original', 'New'])  # Write header
            for _org_path, (new_filename, _ex) in renames.items():
                org_path = Path(_org_path)
                if not org_path.exists():
                    logger.warning(f"Skipping {org_path} because it does not exist")
                    continue
                dir_path = Path(org_path).parent
                new_path = dir_path / new_filename
                if new_path != org_path and not os.path.exists(new_path):
                    os.rename(org_path, new_path)
                    if writer:
                        writer.writerow([str(org_path), str(new_filename)])
            if f:
                f.close()
        except Exception as e:
            logger.error(f"Error applying renames: {e}")
            raise

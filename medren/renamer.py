import csv
import glob
import logging
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from medren.backends import ExifClass, available_backends, backend_support, extension_normalized
from medren.consts import DEFAULT_DATETIME_FORMAT, DEFAULT_TEMPLATE, DEFAULT_SEPARATOR, GENERIC_PATTERNS, \
    DEFAULT_EXIF_FORMAT

logger = logging.getLogger(__name__)

MEDREN_DIR = Path(os.path.join(os.path.expanduser('~'), 'medren'))
MEDREN_DIR.mkdir(parents=True, exist_ok=True)
PROFILES_DIR = MEDREN_DIR / 'PROFILEs'
PROFILES_DIR.mkdir(parents=True, exist_ok=True)


def calc_sha256(path) -> str:
    pass


@dataclass
class Renamer:
    """A class to handle media file renaming based on metadata."""
    prefix: str = field(default='')  # The prefix to use for renamed files
    suffix: str = field(default='')  # The suffix to use for renamed files
    template: str = field(default=DEFAULT_TEMPLATE)  # The template to use for the new filename
    datetime_format: str = field(default=DEFAULT_DATETIME_FORMAT)  # The format to use for the datetime
    exif_format: str = field(default=DEFAULT_EXIF_FORMAT)  # The format to use for the exif
    normalize: bool = field(default=True)  # Whether to normalize the filename
    separators: dict[str, str] | None = None
    backends: list[str] | None = None  # The backends to use for metadata extraction
    recursive: bool = field(default=False)  # Whether to recursively search for files

    def __post_init__(self):
        """Initialize backends after instance creation."""
        self.prefix = self.prefix or ''
        self.backends = self.backends or available_backends

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
            paths = list(glob.glob(str(path)))
            resolved_inputs.extend(paths)
        resolved_inputs = [Path(p) for p in resolved_inputs]
        return resolved_inputs

    def generate_renames(self, inputs: list[Path | str],
                         resolve_names: bool = False) -> dict[str, tuple[Path, ExifClass, str]]:
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
            ex = self.fetch_meta(path)
            if ex is not None:
                dt_and_paths.append((Path(path), ex))
                logger.debug(f"Fetched datetime {ex.dt} ({ex.goff=}) for {path} using {ex.backend}")
        dt_and_paths.sort(key=lambda x: x[1].dt)

        s = self.separators.get('s', DEFAULT_SEPARATOR)
        si = self.separators.get('si', s) if re.search(r'{idx(?::\d+d)?}', self.template) else ''
        sp = self.separators.get('sp', s)
        sn = self.separators.get('sn', s) if '{name}' in self.template else ''
        se = self.separators.get('se', s) if '{exif}' in self.template else ''
        sd = self.separators.get('sd', s) if '{datetime}' in self.template else ''

        do_calc_sha256 = '{sha256}' in self.template
        for path, ex in dt_and_paths:
            try:
                name = path.stem
                clean_name = self.get_clean_name(name)
                suffix = self.suffix
                ext = path.suffix
                datetime_str = ex.dt.strftime(self.datetime_format)
                exif_str = ex.exif_string(self.exif_format, s=s)
                sha256 = calc_sha256(path) if do_calc_sha256 else ''
                # Format the new filename using the template
                new_name = self.template.format(
                    prefix=self.prefix,
                    datetime=datetime_str,
                    name=name,
                    cname=clean_name,
                    suffix=suffix,
                    idx=idx,
                    exif=exif_str,
                    sha256=sha256,
                    s=s,
                    si=si,
                    sp=sp,
                    sn=sn if clean_name else '',
                    se=se if exif_str else '',
                    sd=sd if datetime_str else '',
                    ext=ext,
                )
                new_name = Path(new_name)

                # Remove trailing separators from the new filename
                new_stem, ext = os.path.splitext(new_name)
                for sep in self.separators.values():
                    if sep and new_stem.endswith(sep):
                        new_stem = new_stem[:-len(sep)]
                cnt = counter[new_name]
                if cnt > 0:
                    # Insert counter before the extension
                    new_stem = f"{clean_name}-{cnt}"
                new_name = new_stem + new_name.suffix

                counter[new_name] += 1
                renames[path] = (new_name, ex, exif_str)
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

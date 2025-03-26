import glob
import importlib.util 
import datetime
import logging
import os
import csv
import re
from collections import defaultdict
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from medren.backends import backend_support, available_backends
from pathlib import Path

logger = logging.getLogger(__name__)

MEDREN_DIR = Path(os.path.join(os.path.expanduser('~'), 'medren'))
MEDREN_DIR.mkdir(parents=True, exist_ok=True)
PROFILES_DIR = MEDREN_DIR / 'PROFILEs'
PROFILES_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_PROFILE_NAME = 'default'
    
# Generic filename patterns
DAY_PATTERN = r'0[1-9]|[12]\d|3[01]'
MONTH_PATTERN = r'0[1-9]|1[0-2]'
HOUR_PATTERN = r'[01]\d|2[0-3]'
MINUTE_PATTERN = r'[0-5]\d'
SECOND_PATTERN = r'[0-5]\d'
SEP = r'[-_ ]?'
YEAR_PATTERN = r'\d{4}'

GENERIC_PATTERNS: List[str] = [
    r'^IMG[_-]?\d+', 
    r'^DSC[_-]?\d+', 
    r'^VID[_-]?\d+', 
    r'^MOV[_-]?\d+',
    r'^PXL[_-]?\d+',
    r'^Screenshot[_-]?\d+',
    r'^Photo[_-]?\d+',
    f'^{YEAR_PATTERN}{SEP}({DAY_PATTERN}){SEP}({DAY_PATTERN}){SEP}({HOUR_PATTERN}){SEP}({MINUTE_PATTERN})({SEP}{SECOND_PATTERN})?',
]

DEFAULT_TEMPLATE = '{prefix}{sp}#{idx:03d}{si}{datetime}{sd}{name}{sn}{suffix}{ext}'
DEFAULT_SEPERATOR = '_'
DEFAULT_DATETIME_FORMAT = '%Y-%m-%d-%H-%M-%S'

@dataclass
class Renamer:
    """A class to handle media file renaming based on metadata."""
    prefix: str = field(default='')  # The prefix to use for renamed files
    suffix: str = field(default='')  # The suffix to use for renamed files
    template: str = field(default=DEFAULT_TEMPLATE)  # The template to use for the new filename
    datetime_format: str = field(default=DEFAULT_DATETIME_FORMAT)  # The format to use for the datetime
    normalize: bool = field(default=True)  # Whether to normalize the filename
    si: str = field(default=DEFAULT_SEPERATOR)  # The separator to use for the index
    sp: str = field(default=DEFAULT_SEPERATOR)  # The separator to use for the prefix
    sd: str = field(default=DEFAULT_SEPERATOR)  # The separator to use for the datetime
    sn: str = field(default=DEFAULT_SEPERATOR)  # The separator to use for the name
    backends: list[str] | None = None  # The backends to use for metadata extraction

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

    def get_name(self, basename: str) -> str:
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

    def fetch_datetime(self, path: str) -> datetime.datetime | None:
        """
        Extract datetime from file metadata.
        
        Args:
            path: Path to the file
            
        Returns:
            datetime.datetime | None: The extracted datetime or None if not found
        """
        try:
            ext = os.path.splitext(path)[1].lower()
            for backend in self.backends:
                supported_exts = backend_support[backend].extensions
                if supported_exts is None or ext in supported_exts:
                    return backend_support[backend].extract_func(path)
        except Exception as e:
            logger.error(f"Error extracting datetime from {path}: {e} using {self.backends}")
        return None

    def resolve_names(self, inputs: List[Path | str]) -> List[Path]:
        """
        Resolve names from inputs.
        
        Args:
            inputs: List of input paths
        """
        resolved_inputs =[]
        for path in inputs:
            path = Path(path)
            if path.is_dir():
                if self.recursive:
                    path = path / '**/*'
                else:
                    path = path / '*'
            elif path.is_file():
                path = path.parent / path.name
            paths = list(glob.glob(str(path)))
            resolved_inputs.extend(paths)
        return resolved_inputs
    
    def generate_renames(self, inputs: List[Path | str], resolve_names: bool = False) -> Dict[str, str]:
        """
        Generate a preview of file renames.
        
        Args:
            directory: Directory containing files to rename
            
        Returns:
            Dict[str, str]: Dictionary mapping original filenames to new filenames
        """
        if resolve_names:
            inputs = self.resolve_names(inputs)
        renames, counter = {}, defaultdict(int)
        idx = 0
        dt_and_paths = []
        for path in inputs:
            dt = self.fetch_datetime(path)
            if dt:
                dt_and_paths.append((dt, path))
        dt_and_paths.sort()
        
        for dt, path in dt_and_paths:
            try:
                path = Path(path)
                stem = path.stem
                name = self.get_name(stem)
                suffix = self.suffix
                ext = os.path.splitext(path)[1]
                datetime_str = dt.strftime(self.datetime_format)
                
                # Format the new filename using the template
                new_name = self.template.format(
                    prefix=self.prefix,
                    datetime=datetime_str,
                    stem=stem,
                    name=name,
                    suffix=suffix,
                    idx=idx,
                    sp=self.sp if '{prefix}' in self.template and self.prefix else '',
                    si=self.si if re.search(r'{idx(?::\d+d)?}', self.template) else '',
                    sn=self.sn if '{name}' in self.template and name else '',
                    sd=self.sd if '{datetime}' in self.template and datetime_str else '',
                    ext=ext
                )      
                new_name = Path(new_name)           

                # Remove trailing separators from the new filename
                new_stem, ext = os.path.splitext(new_name)
                for sep in [self.sp, self.sn, self.sd, self.si]:
                    if new_stem.endswith(sep):
                        new_stem = new_stem[:-len(sep)]                
                cnt = counter[new_name]
                if cnt > 0:
                    # Insert counter before the extension
                    new_stem = f"{name}-{cnt}"
                new_name = new_stem + new_name.suffix
                
                counter[new_name] += 1
                renames[path] = new_name
                idx += 1
            except Exception as e:
                logger.error(f"Error generating preview for {path}: {e}")
        return renames
        
    def apply_rename(self, renames: Dict[str, str], logfile: Path | str | None = None) -> None:
        """
        Apply the renaming operations.
        
        Args:
            directory: Directory containing files to rename
            renames: Dictionary mapping original filenames to new filenames
        """
        try:
            f = None
            if logfile:
                logfile = Path(logfile)
                logfile.parent.mkdir(parents=True, exist_ok=True)
                f = open(logfile, 'w', newline='', encoding='utf-8')
                writer = csv.writer(f)
                writer.writerow(['Original', 'New'])  # Write header
            for original_path, new_filename in renames.items():
                original_path = Path(original_path)
                if not original_path.exists():
                    logger.warning(f"Skipping {original_path} because it does not exist")
                    continue
                dir = Path(original_path).parent
                new_path = dir / new_filename
                if new_path != original_path and not os.path.exists(new_path):
                    os.rename(original_path, new_path)
                    if f:
                        writer.writerow([str(original_path), str(new_filename)])
            if f:
                f.close()
        except Exception as e:
            logger.error(f"Error applying renames in {dir}: {e}")
            raise

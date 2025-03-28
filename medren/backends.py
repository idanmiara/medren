import importlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from medren.exif_process import ExifClass, ExifStat, extract_datetime_local, extract_datetime_utc, parse_offset

image_ext_with_exif = ['.jpg', '.jpeg', '.tif', '.tiff']
image_extensions = [*image_ext_with_exif, '.png', '.bmp', '.heic']

def extract_piexif(path: str, logger: logging.Logger) -> ExifClass | None:
    from medren.backend_piexif import piexif_get, piexif_get_raw
    exif_dict, stat = piexif_get_raw(path, logger)
    if stat == ExifStat.ValidExif:
        ex, stat = piexif_get(exif_dict, ext=Path(path).suffix, logger=logger)
        if stat == ExifStat.ValidExif:
            return ex
    return None

def extract_exiftool(path: str, logger: logging.Logger) -> ExifClass | None:
    import exiftool
    try:
        with exiftool.ExifToolHelper() as et:
            metadata = et.get_metadata(path)
            if metadata and len(metadata) > 0:
                metadata = metadata[0]
                date_str = metadata.get('MakerNotes:TimeStamp') or \
                    metadata.get('EXIF:DateTimeOriginal') or \
                        metadata.get('QuickTime:CreateDate')
                if date_str:
                    dt, goff = extract_datetime_utc(date_str, logger)
                    return ExifClass(backend='exiftool', ext=Path(path).suffix, dt=dt, goff=goff)
    except Exception as e:
        logger.debug(f"Could not extract datetime from {path}: {e} using exiftool")
    return None


def extract_exifread(path: str, logger: logging.Logger) -> ExifClass | None:
    import exifread
    with open(path, 'rb') as f:
        tags = exifread.process_file(f, stop_tag='EXIF DateTimeOriginal')
        date_tag = tags.get('EXIF DateTimeOriginal')
        if date_tag:
            dt, _ = extract_datetime_utc(date_tag.values, logger)
            offset_tag = tags.get('EXIF OffsetTime')
            if offset_tag:
                goff = parse_offset(offset_tag.values, logger)
            return ExifClass(backend='exifread', ext=Path(path).suffix, dt=dt, goff=goff)
    return None

def extract_hachoir(path: str, logger: logging.Logger) -> ExifClass | None:
    from hachoir.metadata import extractMetadata
    from hachoir.parser import createParser

    parser = createParser(path)
    try:
        metadata = extractMetadata(parser) if parser else None
        if metadata:
            for item in metadata.exportPlaintext():
                if "Creation date" in item:
                    date_str = item.split(": ")[1]
                    dt, goff = extract_datetime_local(date_str, logger)
                    return ExifClass(backend='hachoir', ext=Path(path).suffix, dt=dt, goff=goff)

    finally:
        if parser:
            parser.stream._input.close()
    return None

def extract_pymediainfo(path: str, logger: logging.Logger) -> ExifClass:
    from pymediainfo import MediaInfo
    media_info = MediaInfo.parse(path)
    for track in media_info.tracks:
        if track.track_type == 'General' and track.encoded_date:
            date_str = track.encoded_date.split('UTC')[0].strip()
            dt, goff = extract_datetime_local(date_str, logger)
            return ExifClass(backend='pymediainfo', ext=Path(path).suffix, dt=dt, goff=goff)
    return None

def extract_ffmpeg(path: str, logger: logging.Logger) -> ExifClass | None:
    import ffmpeg
    probe = ffmpeg.probe(path)
    date_str = probe['format']['tags'].get('creation_time')
    if date_str:
        date_str = date_str.split('.')[0].replace('T', ' ')
        dt, goff = extract_datetime_local(date_str, logger)
        return ExifClass(backend='ffmpeg', ext=Path(path).suffix, dt=dt, goff=goff)
    return None


@dataclass
class Backend:
    name: str
    ext: list[str]
    func: Callable[[str, logging.Logger], ExifClass | None]
    dep: list[str]

backend_priority = [
    'piexif',
    'exifread',
    'exiftool',
    'hachoir',
    'pymediainfo',
    'ffmpeg'
    ]
available_backends = [backend for backend in backend_priority if importlib.util.find_spec(backend)]

backend_support = {
    'piexif': Backend(name='piexif', ext=image_ext_with_exif, func=extract_piexif, dep=[]),
    'exifread': Backend(name='exifread', ext=None, func=extract_exifread, dep=[]),
    'exiftool': Backend(name='exiftool', ext=None, func=extract_exiftool, dep=['exiftool.exe']),
    'hachoir': Backend(name='hachoir', ext=None, func=extract_hachoir, dep=['hachoir-metadata.exe']),
    'pymediainfo': Backend(name='pymediainfo', ext=None, func=extract_pymediainfo, dep=['MediaInfo.dll']),
    'ffmpeg': Backend(name='ffmpeg', ext=None, func=extract_ffmpeg, dep=['ffprobe.exe']),
}

import importlib
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from medren.backend_piexif import get_best_dt
from medren.consts import image_ext_with_exif
from medren.datetime_from_filename import extract_datetime_from_filename
from medren.exif_process import ExifClass, ExifStat, parse_datetime_dash, extract_datetime_with_optional_goff, parse_offset, \
    fix_make_model, parse_datetime_colon


def extract_piexif(path: Path | str, logger: logging.Logger) -> ExifClass | None:
    from medren.backend_piexif import piexif_get
    ex, stat = piexif_get(path, logger=logger)
    if stat == ExifStat.ValidExif:
        return ex
    return None


def extract_exiftool(path: Path | str, logger: logging.Logger) -> ExifClass | None:
    import exiftool
    from exiftool.exiftool import ENCODING_UTF8
    path = Path(path)
    with (exiftool.ExifToolHelper(encoding=ENCODING_UTF8) as et):
        metadata = et.get_metadata(str(path))
        if metadata and len(metadata) > 0:
            metadata = metadata[0]
            exif_date = metadata.get('EXIF:DateTimeOriginal')
            date_str = exif_date or \
                        metadata.get('MakerNotes:TimeStamp') or \
                        metadata.get('QuickTime:CreateDate')
            if date_str:
                dt, goff = extract_datetime_with_optional_goff(date_str, logger)
                is_utc = goff is None and exif_date is None
                lat = metadata.get('Composite:GPSLatitude')
                lon = metadata.get('Composite:GPSLongitude')
                make, model = fix_make_model(metadata.get('MakerNotes:Make'), metadata.get('MakerNotes:Model'))
                if not lat or not lon:
                    latlon = metadata.get('Composite:GPSPosition', metadata.get('QuickTime:GPSCoordinates'))
                    if latlon:
                        try:
                            lat, lon = str(latlon).split(' ')
                            lat = float(lat)
                            lon = float(lon)
                        except Exception:
                            lat, lon = None, None
                return ExifClass(backend='exiftool', ext=path.suffix, dt=dt, goff=goff, lat=lat, make=make, model=model, lon=lon, is_utc=is_utc)
    return None


def extract_exifread(path: Path | str, logger: logging.Logger) -> ExifClass | None:
    import exifread
    from exifread.classes import IfdTag

    def parse_gps_tag(p: IfdTag, ref: IfdTag) -> float | None:
        if not p:
            return None
        p = p.values
        ref = ref.values
        d = p[0].num / p[0].den
        m = p[1].num / p[1].den
        s = p[2].num / p[2].den
        dms = d + m / 60 + s / 3600
        if ref in ['S', 'W']:
            return -dms
        return dms

    def get_tag_str(p: IfdTag) -> str | None:
        if not p:
            return None
        return p.values

    def get_tag_int(p: IfdTag) -> int | None:
        if not p:
            return None
        return p.values[0]

    def get_tag_float(p: IfdTag, digits: int) -> float | None:
        if not p:
            return None
        p = p.values
        p = p[0].num / p[0].den
        if digits:
            p = round(p, digits)
        return p

    def get_offset_tag(p: IfdTag) -> int | None:
        if not p:
            return None
        return parse_offset(p.values, logger)

    path = Path(path)
    with open(path, 'rb') as f:
        tags = exifread.process_file(f)
        t_org = get_tag_str(tags.get('EXIF DateTimeOriginal'))
        t_dig = get_tag_str(tags.get('EXIF DateTimeDigitized'))
        dt, stat = get_best_dt([t_org, t_dig])
        if dt is None:
            return None
        t_img = get_tag_str(tags.get('Image DateTime'))
        t_fn = extract_datetime_from_filename(path.name)
        dt = parse_datetime_colon(t_org)

        goff_org = get_offset_tag(tags.get('EXIF OffsetTimeOriginal'))
        goff_dig = get_offset_tag(tags.get('EXIF OffsetTimeDigitized'))
        goff_img = get_offset_tag(tags.get('EXIF OffsetTime'))

        make = get_tag_str(tags.get('Image Make'))
        model = get_tag_str(tags.get('Image Model'))
        make, model = fix_make_model(make, model)

        w = get_tag_int(tags.get('EXIF ExifImageWidth'))
        h = get_tag_int(tags.get('EXIF ExifImageLength'))

        iw = get_tag_int(tags.get('Image ImageWidth'))
        ih = get_tag_int(tags.get('Image ImageLength'))
        # XResolution = get_tag_val(tags.get('Image XResolution'))
        # YResolution = get_tag_val(tags.get('Image YResolution'))

        lat = parse_gps_tag(tags.get('GPS GPSLatitude'), tags.get('GPS GPSLatitudeRef'))
        lon = parse_gps_tag(tags.get('GPS GPSLongitude'), tags.get('GPS GPSLongitudeRef'))
        alt = get_tag_float(tags.get('GPS GPSAltitude'), 1)
        ex = ExifClass(
            ext=path.suffix,

            dt=dt,
            is_utc=False,
            t_org=t_org,
            t_dig=t_dig,
            t_img=t_img,
            t_fn=t_fn,

            goff=goff_org,
            goff_dig=goff_dig,
            goff_img=goff_img,

            make=make,
            model=model,

            w=w,
            h=h,
            iw=iw,
            ih=ih,

            lat=lat,
            lon=lon,
            alt=alt,

            backend='exifread',
        )
        # ex.goff_form_loc(logger=logger)
        return ex


def extract_hachoir(path: Path | str, logger: logging.Logger) -> ExifClass | None:
    from hachoir.metadata import extractMetadata
    from hachoir.parser import createParser
    path = Path(path)
    parser = createParser(str(path))
    t_org = t_dig = t_img = dt = goff_org = goff_dig = goff_img = make = model = w = h = iw = ih = lat = lon = alt = None
    try:
        metadata = extractMetadata(parser) if parser else None
        if metadata:
            for item in metadata.exportPlaintext():
                try:
                    tag_name, tag_val = item.split(": ")
                except Exception:
                    continue
                tag_name = tag_name[2:]
                if tag_name == "Image width":
                    iw = int(tag_val[:-7])  # pixels
                elif tag_name == "Image height":
                    ih = int(tag_val[:-7])
                elif tag_name == "Camera model":
                    model = tag_val
                elif tag_name == "Camera manufacturer":
                    make = tag_val
                elif tag_name == "Date-time original":
                    t_org = tag_val.replace('-', ':')
                elif tag_name == "Date-time digitized":
                    t_dig = tag_val.replace('-', ':')
                elif tag_name == "Creation date":
                    if not t_img:
                        # sometimes this entry appears twice (why?), the first occurrence is the correct one
                        t_img = tag_val.replace('-', ':')
                elif tag_name == "Latitude":
                    lat = float(tag_val)
                elif tag_name == "Longitude":
                    lon = float(tag_val)
                elif tag_name == "Altitude":
                    alt = round(float(tag_val[:-7]), 1)  # meters

            if not t_org and not t_dig:
                return None
            dt = parse_datetime_colon(t_org or t_dig)
            make, model = fix_make_model(make, model)
            t_fn = extract_datetime_from_filename(path.name)
            return ExifClass(
                ext=path.suffix,

                dt=dt,
                is_utc=False,
                t_org=t_org,
                t_dig=t_dig,
                t_img=t_img,
                t_fn=t_fn,

                goff=goff_org,
                goff_dig=goff_dig,
                goff_img=goff_img,

                make=make,
                model=model,

                w=w,
                h=h,
                iw=iw,
                ih=ih,

                lat=lat,
                lon=lon,
                alt=alt,

                backend='hachoir',
            )

    finally:
        if parser:
            parser.stream._input.close()
    return None


def extract_pymediainfo(path: Path | str, logger: logging.Logger) -> ExifClass | None:
    from pymediainfo import MediaInfo
    path = Path(path)
    media_info = MediaInfo.parse(path)
    for track in media_info.tracks:
        if track.track_type == 'General' and track.encoded_date:
            date_str = track.encoded_date.split('UTC')[0].strip()
            dt = parse_datetime_dash(date_str, logger)
            is_utc = True
            try:
                lat, lon = parse_location_string(track.xyz)
            except Exception:
                lat, lon = None, None
            return ExifClass(backend='pymediainfo', ext=path.suffix, dt=dt, lat=lat, lon=lon, is_utc=is_utc)
    return None


def parse_location_string(s: str) -> tuple[float | None, float | None]:
    if not s:
        return None, None
    # '+32.1234+034.1234/'
    pattern = r'([+-]\d+\.\d+)([+-]\d+\.\d+)/'
    match = re.match(pattern, s)
    if match:
        lat = float(match.group(1))
        lon = float(match.group(2))
        return lat, lon
    return None, None


def parse_goff_string(s: str) -> float | None:
    # +0300 means +03:00
    if not s:
        return None
    try:
        s = float(s)
        h = s / 100
        m = s % 100
        return h + m/60
    except Exception:
        return None


def extract_ffmpeg(path: Path | str, logger: logging.Logger) -> ExifClass | None:
    import ffmpeg
    path = Path(path)
    try:
        probe = ffmpeg.probe(str(path))
    except Exception:
        return None
    tags = probe['format'].get('tags')
    if not tags:
        return None
    date_str = tags.get('creation_time')
    if date_str:
        date_str = date_str.split('.')[0].replace('T', ' ')
        dt = parse_datetime_dash(date_str, logger)
        is_utc = True
        lat, lon = parse_location_string(tags.get('location'))
        goff = parse_goff_string(tags.get('com.samsung.android.utc_offset'))
        make, model = fix_make_model(tags.get('maker'), tags.get('model'))
        return ExifClass(backend='ffmpeg', ext=path.suffix, make=make, model=model, dt=dt, goff=goff, lat=lat, lon=lon, is_utc=is_utc)
    return None


@dataclass
class Backend:
    module: str
    package: str
    ext: list[str] | None
    func: Callable[[Path | str, logging.Logger], ExifClass | None]
    dep: list[str]


backend_support = {b.module: b for b in [
    Backend(module='exifread', package='exifread', ext=None, func=extract_exifread, dep=[]),
    Backend(module='piexif', package='piexif', ext=image_ext_with_exif, func=extract_piexif, dep=[]),
    Backend(module='exiftool', package='pyexiftool', ext=None, func=extract_exiftool, dep=['exiftool.exe']),
    Backend(module='hachoir', package='hachoir', ext=None, func=extract_hachoir, dep=['hachoir-metadata.exe']),
    Backend(module='pymediainfo', package='pymediainfo', ext=None, func=extract_pymediainfo, dep=['MediaInfo.dll']),
    Backend(module='ffmpeg', package='ffmpeg-python', ext=None, func=extract_ffmpeg, dep=['ffprobe.exe']),
]
                   }

backend_priority = list(backend_support.keys())
available_backends = [backend for backend in backend_priority if importlib.util.find_spec(backend)]
print(available_backends)

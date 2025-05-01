import datetime
import importlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Any

from medren.backend_piexif import get_best_dt
from medren.consts import image_ext_with_exif
from medren.datetime_from_filename import extract_datetime_from_filename
from medren.exif_process import ExifClass, ExifStat, extract_datetime_local, extract_datetime_utc, parse_offset, \
    fix_make_model, parse_exif_datetime
from medren.timezone_offset import get_timezone_offset


def extract_piexif(path: Path | str, logger: logging.Logger) -> ExifClass | None:
    from medren.backend_piexif import piexif_get, piexif_get_raw
    ex, stat = piexif_get(path, logger=logger)
    if stat == ExifStat.ValidExif:
        return ex
    return None


def extract_exiftool(path: Path | str, logger: logging.Logger) -> ExifClass | None:
    import exiftool
    path = str(path)
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

    with open(path, 'rb') as f:
        tags = exifread.process_file(f)
        t_org = get_tag_str(tags.get('EXIF DateTimeOriginal'))
        t_dig = get_tag_str(tags.get('EXIF DateTimeDigitized'))
        dt, stat = get_best_dt([t_org, t_dig])
        if dt is None:
            return None
        t_img = get_tag_str(tags.get('Image DateTime'))
        t_fn = extract_datetime_from_filename(path.name)
        dt = parse_exif_datetime(t_org)

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
            ext=Path(path).suffix,

            dt=dt,
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
    t_org = t_dig = t_img = dt = goff_org = goff_dig = goff_img = make = model = w = h = lat = lon = alt = None
    try:
        metadata = extractMetadata(parser) if parser else None
        if metadata:
            for item in metadata.exportPlaintext():
                try:
                    tag_name, tag_val = item.split(": ")
                except:
                    continue
                tag_name = tag_name[2:]
                if tag_name == "Image width":
                    iw = int(tag_val[:-7]) # pixels
                elif tag_name == "Image height":
                    ih = int(tag_val[:-7])
                elif tag_name == "Camera model":
                    model = tag_val
                elif tag_name == "Camera manufacturer":
                    make = tag_val
                elif tag_name == "Date-time original":
                    t_org = tag_val.replace('-',':')
                elif tag_name == "Date-time digitized":
                    t_dig = tag_val.replace('-',':')
                elif tag_name == "Creation date":
                    t_img = tag_val.replace('-',':')
                elif tag_name == "Latitude":
                    lat = float(tag_val)
                elif tag_name == "Longitude":
                    lon = float(tag_val)
                elif tag_name == "Altitude":
                    alt = round(float(tag_val[:-7]), 1) # meters

            if not t_org and not t_dig:
                return None
            dt = parse_exif_datetime(t_org or t_dig)
            make, model = fix_make_model(make, model)
            t_fn = extract_datetime_from_filename(path.name)
            return ExifClass(
                ext=path.suffix,

                dt=dt,
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
    media_info = MediaInfo.parse(path)
    for track in media_info.tracks:
        if track.track_type == 'General' and track.encoded_date:
            date_str = track.encoded_date.split('UTC')[0].strip()
            dt, goff = extract_datetime_local(date_str, logger)
            return ExifClass(backend='pymediainfo', ext=Path(path).suffix, dt=dt, goff=goff)
    return None


def extract_ffmpeg(path: Path | str, logger: logging.Logger) -> ExifClass | None:
    import ffmpeg
    path = str(path)
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
    ext: list[str] | None
    func: Callable[[Path | str, logging.Logger], ExifClass | None]
    dep: list[str]


backend_support = {b.name: b for b in [
        Backend(name='exifread', ext=None, func=extract_exifread, dep=[]),
        Backend(name='piexif', ext=image_ext_with_exif, func=extract_piexif, dep=[]),
        Backend(name='pyexiftool', ext=None, func=extract_exiftool, dep=['exiftool.exe']),
        Backend(name='hachoir', ext=None, func=extract_hachoir, dep=['hachoir-metadata.exe']),
        Backend(name='pymediainfo', ext=None, func=extract_pymediainfo, dep=['MediaInfo.dll']),
        Backend(name='ffmpeg-python', ext=None, func=extract_ffmpeg, dep=['ffprobe.exe']),
    ]
}
backend_priority = list(backend_support.keys())
available_backends = [backend for backend in backend_priority if importlib.util.find_spec(backend)]

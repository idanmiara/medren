import logging
from pathlib import Path

import piexif

from medren.exif_process import (
    ExifClass,
    ExifRaw,
    ExifStat,
    fix_make_model,
    is_timestamp_valid,
    parse_exif_datetime,
    parse_gps,
    parse_offset,
)


def exif_decode(s: str | bytes) -> str | None:
    if not s:
        return None
    if isinstance(s, bytes):
        return s.decode("utf-8")
        # return s.decode("ascii")
    return s

def piexif_get_raw(filename: Path | str, logger: logging.Logger) -> tuple[ExifRaw | None, ExifStat]:
    try:
        if not Path(filename).is_file():
            return None, ExifStat.FileNotFound
        # if not ExifClass.is_supported(filename):
            # return None, ExifStat.Unsupported
        exif_dict = piexif.load(str(filename))
        if not exif_dict:
            return None, ExifStat.NoExif

        # for ifd in ("0th", "Exif", "GPS", "1st"):
        #     for tag in exif_dict[ifd]:
        #         print(f'{ifd}: {tag}: {piexif.TAGS[ifd][tag]["name"]}: {exif_dict[ifd][tag]}')

        # 0th: 271: Make: b'Canon'
        # 0th: 272: Model: b'Canon PowerShot A720 IS'
        # 0th: 306: DateTime: b'2008:05:30 16:29:54'
        # Exif: 36867: DateTimeOriginal: b'2008:05:30 16:29:54'
        # Exif: 36868: DateTimeDigitized: b'2008:05:30 16:29:54'
        # Exif: 40962: PixelXDimension: 3264
        # Exif: 40963: PixelYDimension: 2448

        # exif_dict = exif_dict_decode(exif_dict)
        if not any(d for d in exif_dict.values()):
            return None, ExifStat.NoExif

        return exif_dict, ExifStat.ValidExif
    except Exception as e:
        logger.warning(f"Could not get raw exif data from {filename}: {e} using piexif")
        return None, ExifStat.UnknownErr

def piexif_get(exif_dict: ExifRaw, ext: str, logger: logging.Logger) -> tuple[ExifClass | None, ExifStat]:
    try:
        _0th = exif_dict.get('0th', {})
        exif = exif_dict.get('Exif', {})

        # Purpose: The original date and time when the photo was actually taken.
        # Typically the most reliable indicator a photo captured timestamp, especially if directly from a camera.
        t_org = exif_decode(exif.get(piexif.ExifIFD.DateTimeOriginal))
        # Purpose: The date and time when the photo was digitized.
        # In digital cameras, this usually matches DateTimeOriginal, but in scanned images,can be the scanning date.
        t_dig = exif_decode(exif.get(piexif.ExifIFD.DateTimeDigitized))
        # Purpose: The date and time of last modification of the file.
        # This tag often changes when the image is edited or modified by software.
        t_img = exif_decode(_0th.get(piexif.ImageIFD.DateTime))

        goff = parse_offset(exif_decode(exif.get(piexif.ExifIFD.OffsetTimeOriginal)), logger)
        goff_dig = parse_offset(exif_decode(exif.get(piexif.ExifIFD.OffsetTimeDigitized)), logger)
        goff_img = parse_offset(exif_decode(exif.get(piexif.ExifIFD.OffsetTime)), logger)

        if not (t_org or t_dig or t_img):
            return None, ExifStat.NoDateTime
        if not is_timestamp_valid(t_org) and not is_timestamp_valid(t_org) and not is_timestamp_valid(t_org):
            return None, ExifStat.InvalidDateTime

        gps = exif_dict.get('GPS', {})
        make, model = fix_make_model(
            exif_decode(_0th.get(piexif.ImageIFD.Make)),
            exif_decode(_0th.get(piexif.ImageIFD.Model)))
        e = ExifClass(
            ext=ext,

            dt=parse_exif_datetime(t_org),
            t_org=t_org,
            t_dig=t_dig,
            t_img=t_img,

            goff=goff,
            goff_dig=goff_dig,
            goff_img=goff_img,

            make=make,
            model=model,
            w=_0th.get(piexif.ImageIFD.ImageWidth),
            h=_0th.get(piexif.ImageIFD.ImageLength),

            x=exif.get(piexif.ExifIFD.PixelXDimension),
            y=exif.get(piexif.ExifIFD.PixelYDimension),

            lat=parse_gps(gps.get(piexif.GPSIFD.GPSLatitude)),
            lon=parse_gps(gps.get(piexif.GPSIFD.GPSLongitude)),
            backend='piexif',
            # all=exif_dict,
        )
        return e, ExifStat.ValidExif
    except Exception as e:
        logger.warning(f"Could not get exif data from {exif_dict}: {e} using piexif")
        return None, ExifStat.UnknownErr


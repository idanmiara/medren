import datetime
import importlib
from dataclasses import dataclass
from typing import Callable

image_extensions = ['.jpg', '.jpeg', '.png', '.tiff', '.bmp', '.heic']

backend_priority = ['exifread', 'hachoir', 'pymediainfo', 'ffmpeg']
available_backends = [backend for backend in backend_priority if importlib.util.find_spec(backend)] + ['none']

def extract_exifread(path: str) -> datetime.datetime | None:
    import exifread
    with open(path, 'rb') as f:
        tags = exifread.process_file(f, stop_tag='EXIF DateTimeOriginal')
        data_str = str(tags.get('EXIF DateTimeOriginal'))
        if data_str:
            return datetime.datetime.strptime(data_str, '%Y:%m:%d %H:%M:%S')
            
def extract_hachoir(path: str) -> datetime.datetime | None:
    from hachoir.parser import createParser
    from hachoir.metadata import extractMetadata

    parser = createParser(path)
    try:
        metadata = extractMetadata(parser) if parser else None
        if metadata:
            for item in metadata.exportPlaintext():
                if "Creation date" in item:
                    date_str = item.split(": ")[1]
                    return datetime.datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
    finally:
        if parser:
            parser.stream._input.close()
            
def extract_pymediainfo(path: str) -> datetime.datetime | None:
    from pymediainfo import MediaInfo
    media_info = MediaInfo.parse(path)
    for track in media_info.tracks:
        if track.track_type == 'General' and track.encoded_date:
            date_str = track.encoded_date.split('UTC')[0].strip()
            return datetime.datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        
def extract_ffmpeg(path: str) -> datetime.datetime | None:
    import ffmpeg
    probe = ffmpeg.probe(path)
    date_str = probe['format']['tags'].get('creation_time')
    if date_str:
        date_str = date_str.split('.')[0].replace('T', ' ')
        return datetime.datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
    

@dataclass
class Backend:
    name: str
    extensions: list[str]
    extract_func: Callable[[str], datetime.datetime | None]

backend_support = {
    'exifread': Backend(name='exifread', extensions=image_extensions, extract_func=extract_exifread),
    'hachoir': Backend(name='hachoir', extensions=None, extract_func=extract_hachoir),
    'pymediainfo': Backend(name='pymediainfo', extensions=None, extract_func=extract_pymediainfo),
    'ffmpeg': Backend(name='ffmpeg', extensions=None, extract_func=extract_ffmpeg),
}
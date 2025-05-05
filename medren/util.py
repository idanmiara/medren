import re


def filename_safe(dirty: str) -> str:
    return re.sub(r"[/\\?%*:|\"<>\x7F\x00-\x1F]", "-", dirty)

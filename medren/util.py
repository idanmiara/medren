def filename_safe(s: str) -> str:
    chars_to_keep = (' ','.','_')
    return "".join(c for c in s if c.isalnum() or c in chars_to_keep).rstrip()

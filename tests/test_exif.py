from dataclasses import fields
from multiprocessing.util import get_logger
from pathlib import Path

import pytest

from medren.backends import backend_support, available_backends
from medren.exif_process import ExifClass

logger = get_logger()
root = Path(r'c:\dev\medren-test')

@pytest.mark.parametrize("filename", list(Path.glob(root, '*.jpg')))
def test_compare_exif_backends(filename: list[Path], backends=['exifread', 'piexif']):
    e0 = backend_support[backends[0]].func(filename, logger)
    if e0:
        e0.backend = None
    for backend in backends[1:]:
        e1 = backend_support[backend].func(filename, logger)
        if e1:
            e1.backend = None
        assert e1 == e0, (e0, e1)


@pytest.mark.parametrize("filename", list(Path.glob(root, '*.*')))
def test_compare_exif_backends_partial(filename: list[Path], backends=available_backends):
    e0 = None
    for backend in backends:
        # if backend != "hachoir":
        #     continue
        e1 = backend_support[backend].func(filename, logger)
        if not e0:
            e0 = e1
        elif e1:
            for field in fields(e0):
                # print(field.name, getattr(e0, field.name))
                if field.name == 'backend':
                    continue
                v0 = getattr(e0, field.name)
                v1 = getattr(e1, field.name)
                if v0 and v1:
                    # if v0 != v1:
                    #     e1 = backend_support[backend].func(filename, logger)
                    assert v0 == v1, field.name
            # assert e0.dt == e1.dt


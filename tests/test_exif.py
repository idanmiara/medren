from multiprocessing.util import get_logger
from pathlib import Path

import pytest

from medren.backends import backend_support, available_backends

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


@pytest.mark.parametrize("filename", list(Path.glob(root, '*.jpg')))
def test_compare_exif_backends(filename: list[Path], backends=available_backends):
    e0 = backend_support[backends[0]].func(filename, logger)
    for backend in backends[1:]:
        e1 = backend_support[backend].func(filename, logger)
        assert e0.dt == e1.dt


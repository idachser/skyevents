import os

from skyfield.api import Loader

EPHEMERIS_FILE = "de440s.bsp"


def data_dir() -> str:
    """Directory for the ephemeris and other downloaded data files"""

    return os.environ.get("SKYEVENTS_DATA", "data")


def get_loader() -> Loader:
    return Loader(data_dir())


def load_ephemeris():
    """JPL DE440s ephemeris; downloaded into data_dir() on first call"""

    return get_loader()(EPHEMERIS_FILE)


def load_timescale():
    return get_loader().timescale()

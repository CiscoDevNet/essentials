from gve_google import __version__, config
import os


def test_version():
    assert __version__ == "0.1.0"


def test_config():
    assert os.environ.get("GOOGLE_CLOUD_PROJECT"), "no env variable"
    # assert config == False, str(config)
    # print('blah blah')

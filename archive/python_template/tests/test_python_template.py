from pathlib import Path
import sys

# Append the 'src' folder to the path.
# https://fortierq.github.io/python-import/#1st-solution-add-root-to-syspath
path_root = Path(__file__).parents[2]
sys.path.append(str(path_root))

from src.python_template import __version__


def test_version():
    assert __version__ == "0.1.0"

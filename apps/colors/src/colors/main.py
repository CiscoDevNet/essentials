import click
import json
import re

# from .cisco import COLORS
from .tailwind import COLORS
from .colorspacious import find_closest_color

DEFAULT_COLORS = json.dumps(COLORS)

def split_colors(colors: str) -> list:
    """
    Split a simple delimited string of colors.
    """
    return [color.strip() for color in re.split(',|;', colors)]


@click.command()
@click.argument("hex")
@click.option("--colors", default=DEFAULT_COLORS)
def run_find_closest_color(hex: str, colors: str = DEFAULT_COLORS):
    """
    Parse the command line arguments and find the closest color.
    """
    try:
        scoped_colors = json.loads(colors)
    except json.JSONDecodeError:
        scoped_colors = split_colors(colors)

    closest = find_closest_color(hex, scoped_colors)
    assert closest in scoped_colors or closest in scoped_colors.values()

    print(closest)

if __name__ == "__main__":
    run_find_closest_color()

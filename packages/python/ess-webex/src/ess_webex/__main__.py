"""Entry point for ``python -m ess_webex``."""

from dotenv import load_dotenv

from ess_webex.cli import cli

load_dotenv()


def main() -> None:
    cli()  # pylint: disable=no-value-for-parameter


if __name__ == "__main__":
    main()

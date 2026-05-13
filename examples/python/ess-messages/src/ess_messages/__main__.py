"""Entry point for ``python -m ess_messages``."""

from dotenv import load_dotenv

from ess_messages.cli import cli

load_dotenv()


def main() -> None:
    cli()  # pylint: disable=no-value-for-parameter


if __name__ == "__main__":
    main()

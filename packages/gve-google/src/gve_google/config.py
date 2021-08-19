from dotenv import load_dotenv
from pathlib import Path
import os

DEFAULT_ENV = "development"
NODE_ENV = os.getenv("NODE_ENV", DEFAULT_ENV)


def get_this_dir():
    return Path(__file__).parent.resolve()


def get_cwd():
    return Path().resolve()


def get_env_file_path():
    env_file_path = get_cwd() / f".env.{NODE_ENV}"

    is_development = NODE_ENV == DEFAULT_ENV
    is_specific_file_provided = Path(env_file_path).is_file()

    if is_development and not is_specific_file_provided:
        env_file_path = get_cwd() / ".env"

    return env_file_path


load_dotenv(get_env_file_path())

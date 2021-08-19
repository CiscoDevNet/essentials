from dotenv import load_dotenv
from pathlib import Path

this_dir = Path(__file__).parent.resolve()
env_path = this_dir.parent.parent / ".env"

load_dotenv(env_path)

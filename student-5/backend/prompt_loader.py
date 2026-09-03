from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
PROMPT_DIR = BASE_DIR / "student-5" / "prompts"


def load_prompt(filename):
    return (PROMPT_DIR / filename).read_text(encoding="utf-8").strip()
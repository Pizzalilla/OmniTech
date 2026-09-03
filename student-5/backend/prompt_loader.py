import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMPTS_DIR = os.path.join(BASE_DIR, "prompts")


def load_prompt(filename):
    path = os.path.join(PROMPTS_DIR, filename)

    with open(path, "r", encoding="utf-8") as file:
        return file.read()
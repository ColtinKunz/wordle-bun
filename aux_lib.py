from os import getenv
from typing import Dict


def get_prefix(env_name: str) -> str:
    PREFIX = getenv(env_name)

    if PREFIX is None:
        return ""

    return PREFIX


def count_avg_stats(rounds: int, guesses: int, fails: int) -> Dict[str, str]:
    result = dict()

    if rounds > fails:
        result["rounds"] = str(rounds)
        result["average_guesses"] = f"{guesses / (rounds - fails):.2f}"
        result["fails"] = str(fails)

    return result

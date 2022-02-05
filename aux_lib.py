from os import getenv


def get_prefix(env_name: str) -> str:
    PREFIX = getenv(env_name)

    if PREFIX is None:
        return ""

    return PREFIX

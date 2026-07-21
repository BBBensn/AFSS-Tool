import re

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize_name(name: str) -> str:
    return _NON_ALNUM.sub("", name.lower())

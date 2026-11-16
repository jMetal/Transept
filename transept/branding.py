"""The Transept logo: its files (see assets/branding/README.md)."""

from importlib.resources import files
from typing import Final

BRANDING: Final = files("transept") / "assets" / "branding"
MARK: Final = str(BRANDING / "transept_mark.svg")
WORDMARK: Final = str(BRANDING / "transept_wordmark.svg")

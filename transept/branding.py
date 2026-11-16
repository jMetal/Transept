"""The Transept logo: its files (see assets/branding/README.md)."""

from importlib.resources import files
from typing import Final

BRANDING: Final = files("transept") / "assets" / "branding"
MARK: Final = str(BRANDING / "transept_mark.svg")
WORDMARK: Final = str(BRANDING / "transept_wordmark.svg")

# The colours of the logo and the theme, those of the flag of Ecuador, with navy ink.
BLUE: Final = "#034EA2"
YELLOW: Final = "#FFD100"
RED: Final = "#C8102E"
NAVY: Final = "#14213D"
PALE_BLUE: Final = "#EAF0F8"

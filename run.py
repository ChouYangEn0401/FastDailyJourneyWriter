#!/usr/bin/env python
"""Start the app.

    python run.py
"""

import sys

MIN_PYTHON = (3, 11)

# Checked before importing anything else, so an old interpreter gets this
# instead of a SyntaxError or a confusing failure from a dependency.
if sys.version_info < MIN_PYTHON:
    # English first: this runs on whatever old interpreter the user has, where
    # the console encoding is least predictable.
    sys.exit(
        "\n  This app needs Python %d.%d or newer (found %d.%d).\n"
        "  Download: https://www.python.org/downloads/\n"
        "  (需要 Python %d.%d 或更新的版本)\n"
        % (MIN_PYTHON + sys.version_info[:2] + MIN_PYTHON)
    )

from app.main import main  # noqa: E402  (must come after the version check)

if __name__ == "__main__":
    main()

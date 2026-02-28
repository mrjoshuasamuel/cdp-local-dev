"""
Enables:  python -m cdp_dev <command>

This always works because `python` is always on PATH,
even when `cdp-dev` is not yet on PATH.

After first run of any command, cdp-dev.bat is installed
into System32 so `cdp-dev` works everywhere from then on.
"""
from cdp_dev.cli import main

if __name__ == "__main__":
    main()

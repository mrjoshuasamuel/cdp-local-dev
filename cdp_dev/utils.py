import platform
import ctypes

IS_WINDOWS = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"


def is_admin_windows() -> bool:
    """Check if the current user has administrator privileges on Windows."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

import sys
from unittest.mock import MagicMock

# Mock dependencies that are not available in the environment
sys.modules["rich"] = MagicMock()
sys.modules["rich.console"] = MagicMock()
sys.modules["rich.live"] = MagicMock()
sys.modules["rich.table"] = MagicMock()
sys.modules["rich.panel"] = MagicMock()
sys.modules["rich.text"] = MagicMock()
sys.modules["rich.box"] = MagicMock()
sys.modules["yaml"] = MagicMock()
sys.modules["cryptography"] = MagicMock()
sys.modules["cryptography.fernet"] = MagicMock()

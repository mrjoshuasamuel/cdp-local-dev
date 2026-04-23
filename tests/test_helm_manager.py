import pytest
import base64
from cdp_dev.helm_manager import _is_valid_fernet_key

def test_is_valid_fernet_key_valid():
    """Test with a valid Fernet key."""
    # A valid Fernet key is 32 bytes base64url encoded
    key = base64.urlsafe_b64encode(b"a" * 32).decode()
    assert _is_valid_fernet_key(key) is True

def test_is_valid_fernet_key_invalid_base64():
    """Test with an invalid base64 string."""
    assert _is_valid_fernet_key("not-base64!!!") is False

def test_is_valid_fernet_key_wrong_length():
    """Test with a valid base64 string but incorrect length (not 32 bytes)."""
    # 31 bytes
    key_31 = base64.urlsafe_b64encode(b"a" * 31).decode()
    assert _is_valid_fernet_key(key_31) is False

    # 33 bytes
    key_33 = base64.urlsafe_b64encode(b"a" * 33).decode()
    assert _is_valid_fernet_key(key_33) is False

def test_is_valid_fernet_key_empty_string():
    """Test with an empty string."""
    assert _is_valid_fernet_key("") is False

def test_is_valid_fernet_key_non_string():
    """Test with non-string inputs to ensure they return False."""
    assert _is_valid_fernet_key(None) is False
    assert _is_valid_fernet_key(123) is False

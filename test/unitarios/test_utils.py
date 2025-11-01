# tests/test_utils.py
import binascii
from main import hex_to_bytes, bytes_to_hex

def test_hex_roundtrip():
    hx = "C59B3706"
    b = hex_to_bytes(hx)
    assert isinstance(b, bytes)
    assert bytes_to_hex(b).upper() == hx

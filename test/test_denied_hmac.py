import os
from rfid_client import get_nonce, post_verify

UID = "C59B3706"

def main():
    session_id, nonce = get_nonce(UID)
    # HMAC inválido (random 32 bytes en lugar del correcto)
    fake_hmac = os.urandom(32)
    res = post_verify(UID, session_id, fake_hmac)
    print("Resultado esperado DENIED/HMAC_INVALIDO:", res)

if __name__ == "__main__":
    main()

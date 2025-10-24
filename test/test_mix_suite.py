import os, time
from rfid_client import get_nonce, compute_hmac, post_verify

UID_OK = "C59B3706"
UID_NOAUTH = "DEADBEEF"

def ok_case():
    sid, nonce = get_nonce(UID_OK)
    hmac_b = compute_hmac(UID_OK, nonce)
    return post_verify(UID_OK, sid, hmac_b)

def bad_hmac_case():
    sid, nonce = get_nonce(UID_OK)
    fake = os.urandom(32)
    return post_verify(UID_OK, sid, fake)

def expired_case():
    sid, nonce = get_nonce(UID_OK)
    time.sleep(4)  # TTL=3s
    hmac_b = compute_hmac(UID_OK, nonce)
    return post_verify(UID_OK, sid, hmac_b)

def noauth_case():
    sid, nonce = get_nonce(UID_NOAUTH)
    hmac_b = compute_hmac(UID_NOAUTH, nonce)
    return post_verify(UID_NOAUTH, sid, hmac_b)

def main():
    print("OK =>", ok_case())
    print("HMAC inválido =>", bad_hmac_case())
    print("Sesión expirada =>", expired_case())
    print("No autorizado =>", noauth_case())

if __name__ == "__main__":
    main()

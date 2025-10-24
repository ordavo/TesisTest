from rfid_client import get_nonce, compute_hmac, post_verify

UID = "C59B3706"
ATTEMPTS = 10

def main():
    aliases = []
    for i in range(ATTEMPTS):
        session_id, nonce = get_nonce(UID)
        hmac_bytes = compute_hmac(UID, nonce)
        res = post_verify(UID, session_id, hmac_bytes)
        print(f"[{i+1}/{ATTEMPTS}] =>", res)
        if res.get("result") == "OK":
            aliases.append(res.get("alias"))

    print("Aliases devueltos:", aliases)
    # Tip: puedes revisar colisiones o repetidos
    unique = len(set(aliases))
    print(f"Aliases únicos: {unique} de {len(aliases)}")

if __name__ == "__main__":
    main()

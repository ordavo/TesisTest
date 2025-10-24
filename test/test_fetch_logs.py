from rfid_client import get_logs

def main():
    # últimos 20 en general
    print(get_logs(limit=20))
    # últimos 10 del UID registrado
    print(get_logs(uid="C59B3706", limit=10))

if __name__ == "__main__":
    main()

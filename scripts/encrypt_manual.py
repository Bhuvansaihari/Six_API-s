
from cryptography.fernet import Fernet
import getpass

def encrypt_value():
    print("\n🔐 MANUAL VALUE ENCRYPTOR")
    print("==========================")
    
    # 1. Get Key
    key = input("Paste your ENCRYPTION_KEY: ").strip()
    if not key:
        print("❌ Key is required!")
        return

    try:
        f = Fernet(key)
    except Exception as e:
        print(f"❌ Invalid Key: {e}")
        return

    # 2. Get Value
    print("\nEnter the value you want to encrypt (hidden input):")
    # use getpass to hide input if possible, or input() for simplicity in some terminals
    # getpass might not work well in some IDE terminals, fallback to input if needed
    try:
        value = getpass.getpass("Value to encrypt: ").strip()
    except:
        value = input("Value to encrypt: ").strip()
        
    if not value:
        print("❌ Value is required!")
        return

    # 3. Encrypt
    token = f.encrypt(value.encode()).decode()
    
    print("\n✅ ENCRYPTED STRING:")
    print("-" * 20)
    print(token)
    print("-" * 20)
    print("\n👉 Copy the string above (starting with gAAAA...) and paste it into your .env file.")

if __name__ == "__main__":
    encrypt_value()


from cryptography.fernet import Fernet
import os

def generate():
    """Generate a new encryption key."""
    key = Fernet.generate_key()
    print("\n🔐 HERE IS YOUR NEW ENCRYPTION KEY:")
    print("="*50)
    print(key.decode())
    print("="*50)
    print("\n👉 COPY this key and save it in your .env as:")
    print(f"ENCRYPTION_KEY={key.decode()}")
    print("\n(OR save it to a secure file/manager. Do not commit it to Git!)")

if __name__ == "__main__":
    generate()

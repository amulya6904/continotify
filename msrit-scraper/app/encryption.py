from cryptography.fernet import Fernet


def generate_key() -> str:
    """Generate a new Fernet key. Run once — store in .env as FERNET_KEY."""
    return Fernet.generate_key().decode()


def encrypt_password(plain_password: str, fernet_key: str) -> str:
    """Encrypt a plain-text portal password using Fernet AES-128-CBC."""
    f = Fernet(fernet_key.encode())
    return f.encrypt(plain_password.encode()).decode()


def decrypt_password(encrypted_token: str, fernet_key: str) -> str:
    """Decrypt a Fernet-encrypted password. Used at scrape time only."""
    f = Fernet(fernet_key.encode())
    return f.decrypt(encrypted_token.encode()).decode()

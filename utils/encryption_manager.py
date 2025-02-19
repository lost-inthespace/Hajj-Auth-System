# encryption_manager.py

import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

class EncryptionKeyManager:
    def __init__(self, key=None):
        """
        key should be 16, 24, or 32 bytes for AES.
        For demonstration, we store it in memory as plain text.
        In a real system, you'd secure this carefully.
        """
        if key is None:
            # Dummy 16-byte key
            self.key = b"1234567890ABCDEF"
        else:
            self.key = key

    def set_key(self, new_key: bytes):
        """
        Admin can rotate the key by calling this method.
        """
        self.key = new_key

    def get_key(self) -> bytes:
        return self.key

    def encrypt_data(self, plaintext: str) -> str:
        """
        Encrypt plaintext using AES in CBC mode.
        Return base64-encoded ciphertext.
        Using the key as IV is not recommended in production; 
        do something more secure like random IVs stored alongside ciphertext.
        """
        cipher = AES.new(self.key, AES.MODE_CBC, iv=self.key)
        ct_bytes = cipher.encrypt(pad(plaintext.encode('utf-8'), AES.block_size))
        return base64.b64encode(ct_bytes).decode('utf-8')

    def decrypt_data(self, ciphertext_b64: str) -> str:
        """
        Decrypt from base64-encoded ciphertext.
        """
        cipher = AES.new(self.key, AES.MODE_CBC, iv=self.key)
        ct = base64.b64decode(ciphertext_b64)
        pt = unpad(cipher.decrypt(ct), AES.block_size)
        return pt.decode('utf-8')

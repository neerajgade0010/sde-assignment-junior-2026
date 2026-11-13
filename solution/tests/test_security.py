
from security import (
    encrypt_value,
    decrypt_value,
    create_phone_hash
)


def test_encryption_and_decryption():
    original = "Aarav Menon"

    encrypted = encrypt_value(original)

    assert encrypted != original.encode("utf-8")

    decrypted = decrypt_value(encrypted)

    assert decrypted == original


def test_phone_hash_is_deterministic():
    phone = "+919164637454"

    hash_one = create_phone_hash(phone)
    hash_two = create_phone_hash(phone)

    assert hash_one == hash_two


def test_different_phones_have_different_hashes():
    hash_one = create_phone_hash("+919164637454")
    hash_two = create_phone_hash("+919876543210")

    assert hash_one != hash_two


def test_encryption_changes_ciphertext():
    original = "9876543210"

    encrypted_one = encrypt_value(original)
    encrypted_two = encrypt_value(original)

    assert encrypted_one != encrypted_two

    assert decrypt_value(encrypted_one) == original
    assert decrypt_value(encrypted_two) == original

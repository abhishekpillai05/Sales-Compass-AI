from app.auth.security import (
    hash_password,
    verify_password,
)


password = "my_secure_password"

password_hash = hash_password(
    password
)

print("Password hash:")
print(password_hash)


is_correct = verify_password(
    "my_secure_password",
    password_hash,
)

print("\nCorrect password:")
print(is_correct)


is_wrong = verify_password(
    "wrong_password",
    password_hash,
)

print("\nWrong password:")
print(is_wrong)
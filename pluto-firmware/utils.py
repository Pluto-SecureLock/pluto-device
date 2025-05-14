import random

def generate_password(length, level):
    letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    lowercase = "abcdefghijklmnopqrstuvwxyz"
    digits = "0123456789"
    punctuation = "!@#$%^&*()-_=+[]{}|;:,.<>?/"
    if level == 0:
        chars = letters + digits
    elif level == 1:
        chars = lowercase + digits + punctuation
    else:
        chars = letters + digits + punctuation
    return ''.join(random.choice(chars) for _ in range(length))

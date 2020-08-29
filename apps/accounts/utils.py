from random import randrange


def generate_raw_password():
    num = randrange(380204031)
    if num != int(num) or num < 0:
        return None
    letters_case_sensitive = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ"
    reverse_pw = ""
    bases = [48, 48, 48, 48, 48]
    for base in bases:
        if base == 48:
            reverse_pw += letters_case_sensitive[num % base]
        num //= base
    if num != 0 or len(reverse_pw) != len(bases):
        return generate_raw_password()
    return reverse_pw[::-1]

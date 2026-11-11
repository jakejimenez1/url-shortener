import random
import string

# Using alphanumeric characters (a-z, A-Z, 0-9) = 62 characters
# 6 characters = 62^6 = 56 billion possible combinations
def generate_short_code(length: int = 6) -> str:
    characters = string.ascii_letters + string.digits
    return ''.join(random.choices(characters, k=length))

## Alternative: Encode integer ID to base62 string
def encode_id(num: int) -> str:
    characters = string.ascii_letters + string.digits
    base = len(characters)
    
    if num == 0:
        return characters[0]
    
    result = []
    while num:
        result.append(characters[num % base])
        num //= base
    
    return ''.join(reversed(result))

## Decode base62 string back to integer ID
def decode_id(code: str) -> int:
    characters = string.ascii_letters + string.digits
    base = len(characters)
    
    num = 0
    for char in code:
        num = num * base + characters.index(char)
    
    return num

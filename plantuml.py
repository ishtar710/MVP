import zlib

# PlantUML 전용 인코딩 함수
def encode_plantuml(text: str) -> str:
    data = text.encode("utf-8")
    compressed = zlib.compress(data)[2:-4]  # zlib 헤더/푸터 제거
    return encode64(compressed)

def encode6bit(b):
    if b < 10:
        return chr(48 + b)
    b -= 10
    if b < 26:
        return chr(65 + b)
    b -= 26
    if b < 26:
        return chr(97 + b)
    b -= 26
    if b == 0:
        return '-'
    if b == 1:
        return '_'
    return '?'

def append3bytes(b1, b2, b3):
    c1 = b1 >> 2
    c2 = ((b1 & 0x3) << 4) | (b2 >> 4)
    c3 = ((b2 & 0xF) << 2) | (b3 >> 6)
    c4 = b3 & 0x3F
    return encode6bit(c1) + encode6bit(c2) + encode6bit(c3) + encode6bit(c4)

def encode64(data: bytes) -> str:
    res = ""
    i = 0
    while i < len(data):
        b1 = data[i]
        b2 = data[i+1] if i+1 < len(data) else 0
        b3 = data[i+2] if i+2 < len(data) else 0
        res += append3bytes(b1, b2, b3)
        i += 3
    return res

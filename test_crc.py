def crc16_ccitt_false(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return crc

s = '00020201021126560014A000000615000101068900610224602e133f1129ae9ef5dfd3cb5204000053034585802MY5925PERFECT SECURITY & AUT...6002MY8240151624d4b83552c970df6f920824aaf4e04c86e96304'
expected = '762F'
calculated = f'{crc16_ccitt_false(s.encode("ascii")):04X}'
print('Calculated:', calculated, 'Expected:', expected)

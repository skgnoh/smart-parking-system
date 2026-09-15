import base64
import io
import qrcode
from PIL import Image

def crc16_ccitt_false(data: bytes) -> int:
    """
    Computes CRC-16/CCITT-FALSE checksum.
    Polynomial: 0x1021, Initial: 0xFFFF, No reflection, XOR out: 0x0000.
    """
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

class DuitNowDynamicQR:
    def __init__(self, static_raw_payload: str):
        self.raw_payload = static_raw_payload.strip()
        self._validate()

    def _validate(self):
        if not (self.raw_payload.startswith("000201") or self.raw_payload.startswith("000202")):
            raise ValueError("Invalid DuitNow QR Payload format. Must start with '000201' or '000202'.")

    def _parse_tlv(self):
        """
        Parses the EMVCo string into a dictionary of tags and their ordered list.
        Removes Tag 63 (CRC) if present at the end.
        """
        payload = self.raw_payload
        
        # EMVCo CRC is always at the end: 6304 + 4 hex chars = 8 chars
        if len(payload) >= 8 and payload[-8:-4] == "6304":
            payload = payload[:-8]
            
        idx = 0
        tags = {}
        order = []
        
        while idx < len(payload):
            if idx + 4 > len(payload):
                break
            tag = payload[idx:idx+2]
            length_str = payload[idx+2:idx+4]
            try:
                length = int(length_str)
            except ValueError:
                break
            
            value = payload[idx+4:idx+4+length]
            tags[tag] = value
            
            if tag not in order:
                order.append(tag)
                
            idx += 4 + length
            
        return tags, order

    def generate_dynamic_payload(self, amount: float) -> str:
        """
        Generates a new dynamic EMVCo string with the injected amount and a valid checksum.
        Ensures Tag 54 is placed strictly after Tag 53.
        """
        tags, order = self._parse_tlv()
        
        # 1. Update Point of Initiation Method (Tag 01) to '12' (Dynamic)
        tags["01"] = "12"
        if "01" not in order:
            order.insert(1, "01")
            
        # 2. Format and inject Transaction Amount (Tag 54)
        amt_str = f"{amount:.2f}"
        tags["54"] = amt_str
        
        if "54" not in order:
            # Strictly place Tag 54 immediately after Tag 53
            if "53" in order:
                idx_53 = order.index("53")
                order.insert(idx_53 + 1, "54")
            else:
                order.append("54")
                
        # 3. Rebuild the TLV string in order
        out_parts = []
        for tag in order:
            val = tags[tag]
            length_str = f"{len(val):02d}"
            out_parts.append(f"{tag}{length_str}{val}")
            
        base_string = "".join(out_parts)
        
        # 4. Append Tag 63 Identifier + Length (6304)
        base_string += "6304"
        
        # 5. Compute CRC-16 over the rebuilt string
        crc_int = crc16_ccitt_false(base_string.encode('ascii'))
        crc_hex = f"{crc_int:04X}"
        
        return base_string + crc_hex

    def save_qr_image(self, amount: float, filename: str):
        payload = self.generate_dynamic_payload(amount)
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(payload)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        img.save(filename)


if __name__ == "__main__":
    # The real string provided by the user
    REAL_QR = "00020201021126560014A000000615000101068900610224602e133f1129ae9ef5dfd3cb5204000053034585802MY5925PERFECT SECURITY & AUT...6002MY8240151624d4b83552c970df6f920824aaf4e04c86e96304762F"
    
    print("="*60)
    print("   DuitNow EMVCo MPM Dynamic Payload Fixer   ")
    print("="*60)
    print(f"[Original Static]:\n{REAL_QR}\n")
    
    engine = DuitNowDynamicQR(REAL_QR)
    test_amount = 3.00
    dynamic_payload = engine.generate_dynamic_payload(test_amount)
    
    print(f"[Dynamic Reconstructed RM {test_amount:.2f}]:\n{dynamic_payload}\n")
    
    # Verification checks
    print("Verification:")
    print(f" - Contains '010212' (Dynamic Method)? -> {'Yes' if '010212' in dynamic_payload else 'No'}")
    print(f" - Contains '530345854043.00' (Tag 54 immediately after 53)? -> {'Yes' if '530345854043.00' in dynamic_payload else 'No'}")
    
    filename = "test_dynamic_qr.png"
    engine.save_qr_image(test_amount, filename)
    print(f"\n[+] Successfully generated physical QR image: {filename} with Border=4, Error_Correction=M")

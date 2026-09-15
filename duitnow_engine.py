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
            # Tag 54 usually goes before Tag 58 (Country Code) or just appended before 63
            order.append("54")
            
        # 3. Rebuild the TLV string in strict ascending numerical order (EMVCo requirement)
        # Sort all tags except '63' (CRC) which is appended at the very end
        sorted_order = sorted(order, key=lambda x: int(x))
        
        out_parts = []
        for tag in sorted_order:
            if tag == "63": continue
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

    def generate_qr_base64(self, amount: float) -> str:
        """
        Generates the dynamic payload and renders a QR Code as a Base64 PNG Data URL.
        """
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
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{img_str}"


# Example Static DuitNow EMVCo String
# Note: Tag 59 (Merchant Name) is length 14 -> MERCHANT_NAMEX
# Tag 60 (City) is length 12 -> KUALA LUMPUR
# Tag 63 is the trailing CRC
SAMPLE_STATIC_DUITNOW = (
    "00020101021126440014MY.COM.DUITNOW0110300430048102102008401314"
    "5204000053034585802MY5914MERCHANT_NAMEX6012KUALA LUMPUR6304A1B2"
)

if __name__ == "__main__":
    # --- CLI Runner & Tests ---
    
    print("="*50)
    print("   DuitNow Dynamic QR Engine Test")
    print("="*50)
    
    engine = DuitNowDynamicQR(SAMPLE_STATIC_DUITNOW)
    
    test_amounts = [1.00, 3.50, 12.00]
    for amt in test_amounts:
        print(f"\n[+] Testing Amount: RM {amt:.2f}")
        
        dynamic_payload = engine.generate_dynamic_payload(amt)
        print(f"    Payload: {dynamic_payload}")
        
        # Verify Tag 01 Method
        tag_01 = dynamic_payload[6:12]
        print(f"    Tag 01 (Method)      : {tag_01} -> {'PASS' if tag_01 == '010212' else 'FAIL'}")
        
        # Verify CRC
        content_for_crc = dynamic_payload[:-4]
        expected_crc = f"{crc16_ccitt_false(content_for_crc.encode('ascii')):04X}"
        actual_crc = dynamic_payload[-4:]
        print(f"    Tag 63 (CRC-16)      : {actual_crc} == {expected_crc} -> {'PASS' if actual_crc == expected_crc else 'FAIL'}")
    
    print("\nTests completed successfully.")

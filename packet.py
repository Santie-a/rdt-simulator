import zlib

class Packet:
    def __init__(self, type, seq, pkt_id, payload="", ck=None, attempt=1):
        self.type = type        # DATA, ACK, NACK
        self.seq = seq          # 0 or 1
        self.pkt_id = pkt_id    # Incremental ID for logs
        self.payload = payload
        self.attempt = attempt
        self.ck = ck if ck else self.calculate_checksum(payload)

    @staticmethod
    def calculate_checksum(data):
        if data is None:
            data = ""
        # Accept bytes or str-like inputs and ensure consistent unsigned 32-bit CRC
        if isinstance(data, (bytes, bytearray)):
            b = data
        else:
            b = str(data).encode("utf-8")
        return str(zlib.crc32(b) & 0xffffffff)

    def encode(self):
        if self.type == "DATA":
            return f"DATA|seq={self.seq}|id={self.pkt_id}|attempt={self.attempt}|payload={self.payload}|ck={self.ck}"
        elif self.type.startswith("RETRANSMISSION"):
            return f"{self.type}|seq={self.seq}|id={self.pkt_id}|attempt={self.attempt}|payload={self.payload}|ck={self.ck}"
        else:
            return f"{self.type}|seq={self.seq}|id={self.pkt_id}"

    @classmethod
    def decode(cls, raw_str):
        try:
            parts = raw_str.split("|")
            type = parts[0]
            seq = int(parts[1].split("=")[1])
            pkt_id = int(parts[2].split("=")[1])
            payload, ck, attempt = "", "0", 1
            if type == "DATA" or type.startswith("RETRANSMISSION"):
                attempt = parts[3].split("=")[1]
                payload = parts[4].split("=")[1]
                ck = parts[5].split("=")[1]
            return cls(type, seq, pkt_id, payload, ck, attempt)
        except Exception:
            return None
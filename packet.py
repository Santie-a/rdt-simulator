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
        return str(zlib.crc32(data.encode()))

    def encode(self):
        if self.type == "DATA":
            return f"DATA|seq={self.seq}|id={self.pkt_id}|attempt={self.attempt}|payload={self.payload}|ck={self.ck}"
        return f"{self.type}|seq={self.seq}|id={self.pkt_id}"

    @classmethod
    def decode(cls, raw_str):
        try:
            parts = raw_str.split("|")
            type = parts[0]
            seq = int(parts[1].split("=")[1])
            pkt_id = int(parts[2].split("=")[1])
            payload, ck = "", "0"
            if type == "DATA":
                payload = parts[3].split("=")[1]
                ck = parts[4].split("=")[1]
            return cls(type, seq, pkt_id, payload, ck)
        except Exception:
            return None
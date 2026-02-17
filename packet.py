import zlib

class Packet:
    def __init__(self, tipo, seq, pkt_id, payload="", ck=None):
        self.tipo = tipo        # DATA, ACK, NACK
        self.seq = seq          # 0 o 1
        self.pkt_id = pkt_id    # ID incremental para logs
        self.payload = payload
        self.ck = ck if ck else self.calculate_checksum(payload)

    @staticmethod
    def calculate_checksum(data):
        return str(zlib.crc32(data.encode()))

    def encode(self):
        if self.tipo == "DATA":
            return f"DATA|seq={self.seq}|id={self.pkt_id}|payload={self.payload}|ck={self.ck}"
        return f"{self.tipo}|seq={self.seq}|id={self.pkt_id}"

    @classmethod
    def decode(cls, raw_str):
        try:
            parts = raw_str.split("|")
            tipo = parts[0]
            seq = int(parts[1].split("=")[1])
            pkt_id = int(parts[2].split("=")[1])
            payload, ck = "", "0"
            if tipo == "DATA":
                payload = parts[3].split("=")[1]
                ck = parts[4].split("=")[1]
            return cls(tipo, seq, pkt_id, payload, ck)
        except Exception:
            return None
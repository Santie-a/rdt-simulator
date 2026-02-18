import socket
import random
import time
from datetime import datetime
from packet import Packet

def log(message, level="INFO"):
    timestamp = datetime.now().strftime("%M:%S.%f")[:-3]
    log_line = f"[{timestamp}] [{level}] {message}"
    print(log_line)

def ts():
    return datetime.now().strftime("%M:%S.%f")[:-3]  # Remove microseconds for cleaner output

class RDTServer:
    def __init__(self, host="0.0.0.0", port=8080, rdt_version="2.0", p_corrupt=0.2, p_drop=0.2, p_delay=0.2, max_delay=2.5):
        self.host = host
        self.port = port
        self.proto = rdt_version
        self.p_corrupt = p_corrupt
        self.p_drop = p_drop
        self.p_delay = p_delay
        self.max_delay = max_delay
        
        # Protocol state
        self.expected_seq = 0
        self.last_ack_sent = -1  # For RDT 2.2/3.0 when there's an error. Initialize to -1 so it doesn't match valid seq (0 or 1)
        
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def start(self):
        self.sock.bind((self.host, self.port))
        self.sock.listen(1)
        log(f"Servidor RDT {self.proto} iniciado en {self.port}")
        log(f"Configuración: P(Corrupt)={self.p_corrupt}, P(Drop)={self.p_drop}, P(Delay)={self.p_delay}")

        conn, addr = self.sock.accept()
        log(f"Cliente conectado desde {addr}")

        try:
            while True:
                data = conn.recv(2048).decode()
                if not data: break

                pkt = Packet.decode(data)
                if not pkt: continue

                # 1. Packet loss simulation (Only for RDT 3.0)
                if self.proto == "3.0" and random.random() < self.p_drop:
                    log(f"[SIMULACIÓN] PKT con id {pkt.pkt_id} PERDIDO", "WARNING")
                    continue

                # 2. Corruption simulation
                payload_to_check = pkt.payload
                if random.random() < self.p_corrupt:
                    payload_to_check += "X" 
                    log(f"[SIMULACIÓN] PKT con id={pkt.pkt_id}\n CORRUPTO", "WARNING")

                # Group separator for clearer per-packet logs
                log(f"===== MANEJO RX PKT id={pkt.pkt_id} seq={pkt.seq} =====")

                # 3. Integrity check (Checksum)
                rcv_pkt_ck = Packet.calculate_checksum(payload_to_check)
                is_ok = (rcv_pkt_ck == pkt.ck)

                # 4. Response logic according to protocol
                response = self._process_rdt_logic(pkt, is_ok)
                
                if response:
                    # Optionally simulate ACK delay to trigger retransmissions on client
                    if self.p_delay and random.random() < self.p_delay:
                        delay = random.uniform(2, self.max_delay)
                        log(f"[SIMULACIÓN] RETRASO de {delay:.2f}s antes de enviar respuesta para id={pkt.pkt_id}", "WARNING")
                        time.sleep(delay)

                    if self.proto == "2.0":
                        log(f"[R] ENVIAR {response.type} para id={pkt.pkt_id}")
                    else:
                        log(f"[R] ENVIAR {response.type} seq={response.seq} para id={pkt.pkt_id}")
                    try:
                        conn.send(response.encode().encode())
                    except OSError as e:
                        log(f"envío fallido: {e} (el cliente pudo haber cerrado la conexión)", "ERROR")
                        # Do not crash the server on client disconnect; continue to accept/handle next data
                        continue

        except Exception as e:
            log(f"Error: {e}", "ERROR")
        finally:
            conn.close()
            log(f"Conexión cerrada.")

    def _process_rdt_logic(self, pkt, is_ok):
        """Handles the state logic of each protocol."""
        
        if self.proto == "2.0":
            # 2.0: Only checksum matters. No sequence numbers.
            if is_ok:
                log(f"[R] RECIBIDO CORRECTAMENTE (Verif. checksum) {pkt.encode()}")
            else:
                log(f"[R] DATOS CORRUPTOS (inconsistencia checksum). Enviando NACK.", "WARNING")

            resp_type = "ACK" if is_ok else "NACK"
            return Packet(resp_type, pkt.seq, pkt.pkt_id)

        if self.proto == "2.1":
            # 2.1: Checksum + Sequence numbers. Handles duplicates.
            if is_ok and pkt.seq == self.expected_seq:
                log(f"[R] RECIBIDO CORRECTAMENTE (Verif. checksum + SEQ) {pkt.encode()}")
                res = Packet("ACK", pkt.seq, pkt.pkt_id)
                self.expected_seq = 1 - self.expected_seq
                return res
            elif not is_ok:
                log(f"[R] DATOS CORRUPTOS (inconsistencia checksum). Enviando NACK.", "WARNING")
                return Packet("NACK", self.expected_seq, pkt.pkt_id)
            else:
                log(f"[R] DATOS DUPLICADOS (seq recibida={pkt.seq}, esperada={self.expected_seq}). Re-enviando último ACK recibido.")
                return Packet("ACK", pkt.seq, pkt.pkt_id)

        if self.proto in ["2.2", "3.0"]:
            # 2.2 and 3.0: No NACKs. ACK is sent for the last correctly received packet.
            if is_ok and pkt.seq == self.expected_seq:
                log(f"[R] RECIBIDO CORRECTAMENTE {pkt.encode()}")
                log(f"[R] DATOS correctos. Entregando a la APP.")
                res = Packet("ACK", pkt.seq, pkt.pkt_id)
                self.last_ack_sent = self.expected_seq
                self.expected_seq = 1 - self.expected_seq
                return res
            else:
                if not is_ok:
                    log(f"[R] DATOS CORRUPTOS (inconsistencia checksum). Re-enviando ACK del último seq recibido={self.last_ack_sent}", "WARNING")
                elif pkt.seq != self.expected_seq:
                    log(f"[R] DATOS DUPLICADOS (seq recibida={pkt.seq}, esperada={self.expected_seq}). Re-enviando ACK seq={self.last_ack_sent}")
                return Packet("ACK", self.last_ack_sent, pkt.pkt_id)

        return None

if __name__ == "__main__":
    server = RDTServer(rdt_version="3.0", p_corrupt=0.1, p_drop=0.2, p_delay=0.2)
    server.start()
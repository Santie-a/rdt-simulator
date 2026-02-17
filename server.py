import socket
import random
import time
from datetime import datetime
from packet import Packet


def ts():
    return datetime.now().strftime("%M:%S.%f")

class RDTServer:
    def __init__(self, host="0.0.0.0", port=8080, rdt_version="2.0", p_corrupt=0.2, p_drop=0.2, p_delay=0.2, max_delay=4.0):
        self.host = host
        self.port = port
        self.proto = rdt_version
        self.p_corrupt = p_corrupt
        self.p_drop = p_drop
        # Probabilistic ACK delay to provoke sender timeouts and duplicates
        self.p_delay = p_delay
        self.max_delay = max_delay
        
        # Estado del protocolo
        self.expected_seq = 0
        self.last_ack_sent = 1 # Para rdt 2.2 cuando hay error
        
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def start(self):
        self.sock.bind((self.host, self.port))
        self.sock.listen(1)
        print(f"[{ts()}] [*] Servidor RDT {self.proto} iniciado en {self.port}")
        print(f"[{ts()}] [*] Config: P(Corrupt)={self.p_corrupt}, P(Drop)={self.p_drop}, P(Delay)={self.p_delay}")

        conn, addr = self.sock.accept()
        print(f"[{ts()}] [*] Cliente conectado desde {addr}")

        try:
            while True:
                data = conn.recv(2048).decode()
                if not data: break

                pkt = Packet.decode(data)
                if not pkt: continue

                # Group separator for clearer per-packet logs
                print(f"\n[{ts()}] ===== HANDLING PKT id={pkt.pkt_id} seq={pkt.seq} =====")

                # 1. Simulación de PÉRDIDA (Solo rdt 3.0)
                if self.proto == "3.0" and random.random() < self.p_drop:
                    print(f"\n[{ts()}] [SIMULACIÓN] PAQUETE con id {pkt.pkt_id} PERDIDO\n")
                    continue

                # 2. Simulación de CORRUPCIÓN
                payload_to_check = pkt.payload
                if random.random() < self.p_corrupt:
                    payload_to_check += "X" 
                    print(f"\n[{ts()}] [SIMULACIÓN] CORRUPCIÓN EN PAQUETE CON id={pkt.pkt_id}\n")

                # 3. Verificación de Integridad (Checksum)
                rcv_pkt_ck = Packet.calculate_checksum(payload_to_check)
                is_ok = (rcv_pkt_ck == pkt.ck)

                # 4. Lógica de Respuesta según Protocolo
                response = self._process_rdt_logic(pkt, is_ok)
                
                if response:
                    # Optionally simulate ACK delay to trigger retransmissions on client
                    if self.p_delay and random.random() < self.p_delay:
                        delay = random.uniform(self.max_delay * 0.5, self.max_delay)
                        print(f"\n[{ts()}] [SIMULACIÓN] RETRASO de {delay:.2f}s antes de enviar respuesta para id={pkt.pkt_id}\n")
                        time.sleep(delay)

                    if self.proto == "2.0":
                        print(f"[{ts()}] [R] SEND {response.tipo} para id={pkt.pkt_id}")
                    else:
                        print(f"[{ts()}] [R] SEND {response.tipo} seq={response.seq} para id={pkt.pkt_id}")
                    try:
                        conn.send(response.encode().encode())
                    except OSError as e:
                        print(f"\n[{ts()}] [!] send failed: {e} (client may have closed the connection)")
                        # Do not crash the server on client disconnect; continue to accept/handle next data
                        continue

        except Exception as e:
            print(f"\n[{ts()}] [!] Error: {e}")
        finally:
            conn.close()
            print(f"\n[{ts()}] [*] Conexión cerrada.")

    def _process_rdt_logic(self, pkt, is_ok):
        """Maneja la lógica de estados de cada protocolo"""
        
        if self.proto == "2.0":
            # 2.0: Solo importa el checksum. No hay números de secuencia.
            if is_ok:
                print(f"[{ts()}] [R] RECV CORRECTAMENTE {pkt.encode()}")
                print(f"[{ts()}] [R] DATA Correcto. Entregando a APP.")
            else:
                print(f"[{ts()}] [R] DATA CORRUPTO (checksum mismatch). Enviando NACK.")

            resp_type = "ACK" if is_ok else "NACK"
            return Packet(resp_type, pkt.seq, pkt.pkt_id)

        if self.proto == "2.1":
            # 2.1: Checksum + Números de secuencia. Maneja duplicados.
            if is_ok and pkt.seq == self.expected_seq:
                print(f"[{ts()}] [R] RECV CORRECTAMENTE {pkt.encode()}")
                print(f"[{ts()}] [R] DATA Correcto. Entregando a APP.")
                res = Packet("ACK", pkt.seq, pkt.pkt_id)
                self.expected_seq = 1 - self.expected_seq
                return res
            elif not is_ok:
                print(f"[{ts()}] [R] DATA CORRUPTO (checksum mismatch). Enviando NACK.")
                return Packet("NACK", self.expected_seq, pkt.pkt_id)
            else:
                print(f"[{ts()}] [R] DATA DUPLICADO (got seq={pkt.seq}, expected={self.expected_seq}). Re-enviando ACK del último recibido.")
                return Packet("ACK", pkt.seq, pkt.pkt_id)

        if self.proto in ["2.2", "3.0"]:
            # 2.2 y 3.0: Sin NACKs. Se envía ACK del último paquete correcto.
            if is_ok and pkt.seq == self.expected_seq:
                print(f"[{ts()}] [R] RECV CORRECTAMENTE {pkt.encode()}")
                print(f"[{ts()}] [R] DATA Correcto. Entregando a APP.")
                res = Packet("ACK", pkt.seq, pkt.pkt_id)
                self.last_ack_sent = self.expected_seq
                self.expected_seq = 1 - self.expected_seq
                return res
            else:
                # Diferenciar corrupto vs duplicado
                if not is_ok:
                    print(f"[{ts()}] [R] DATA CORRUPTO (checksum mismatch). Re-enviando ACK del último recibido seq={self.last_ack_sent}")
                elif pkt.seq != self.expected_seq:
                    print(f"[{ts()}] [R] DATA DUPLICADO (got seq={pkt.seq}, expected={self.expected_seq}). Re-enviando ACK seq={self.last_ack_sent}")
                return Packet("ACK", self.last_ack_sent, pkt.pkt_id)

        return None

if __name__ == "__main__":
    server = RDTServer(rdt_version="2.1", p_corrupt=0, p_drop=0.1, p_delay=0, max_delay=2.5)
    server.start()
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
    return datetime.now().strftime("%M:%S.%f")[:-3] 

class RDTClient:
    def __init__(self, server_ip, port, rdt_version= 2.0, timeout=None, p_ack_drop=0.0):
        self.server_address = (server_ip, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.timeout = timeout
        self.p_ack_drop = p_ack_drop
        self.rdt_version = rdt_version
        self.current_seq = 0
        self.global_pkt_id = 0

    def connect(self):
        self.sock.connect(self.server_address)
        log(f"Conectado a {self.server_address}")
        log(f"Configuración: P(pérdida ACK/NACK)={self.p_ack_drop}, tiempo de espera={self.timeout}s (Para RDT 3.0)")

    def rdt_send(self, data_list):
        """
        Sends a list of messages following the rules of the selected protocol.
        """
        for message in data_list:
            delivered = False
            attemps = 1
            
            while not delivered:
                # 1. Build packet
                pkt = Packet("DATA", self.current_seq, self.global_pkt_id, message)
                
                # 2. Send and record trace (Required by report)
                log(f"\n===== TX PKT id={pkt.pkt_id} seq={pkt.seq} =====")
                log(f"[S] ENVIAR {pkt.encode()} (Intento {attemps})")
                self.sock.send(pkt.encode().encode())

                try:
                    # 3. Wait for response
                    # Apply timeout for RDT versions that simulate packet loss
                    if self.rdt_version in ["2.1", "2.2", "3.0"] and self.timeout:
                        self.sock.settimeout(self.timeout)
                    else:
                        # blocking mode
                        self.sock.settimeout(None)

                    raw_res = self.sock.recv(1024).decode()
                    res_pkt = Packet.decode(raw_res)

                    # Simulate ACK/NACK loss at the client side AFTER receiving
                    # This ensures the buffer is cleared and loss is properly handled
                    if self.rdt_version in ["2.1", "2.2", "3.0"] and random.random() < self.p_ack_drop:
                        log(f"\n[SIMULACIÓN]: ACK/NACK perdido. Retransmitiendo DATA\n", "WARNING")
                        attemps += 1
                        continue

                    if not res_pkt:
                        log(f"[S] ACK/NACK corrupto -> Ignorar/Retransmitir", "WARNING")
                        attemps += 1
                        continue

                    log(f"===== MANEJO DE RESPUESTA id={res_pkt.pkt_id} seq={res_pkt.seq} =====")
                    if self._check_success(self.rdt_version, res_pkt):
                        log(f"[S] RECIBIDO {res_pkt.type} seq={res_pkt.seq} id={res_pkt.pkt_id} -> OK.")
                        delivered = True
                        # Toggle sequence for 2.1, 2.2 and 3.0
                        if self.rdt_version != "2.0":
                            self.current_seq = 1 - self.current_seq
                        self.global_pkt_id += 1
                    else:
                        # Distinguish corruption (NACK), duplicate/old ACKs, or generic rejection
                        if res_pkt.type == "NACK":
                            log(f"[S] NACK recibido -> Receptor indica corrupción. Retransmitiendo...", "WARNING")
                        elif res_pkt.type == "ACK" and res_pkt.seq != self.current_seq:
                            log(f"[S] ACK seq={res_pkt.seq} id={res_pkt.pkt_id} -> ACK DUPLICADO/ANTIGUO (esperado {self.current_seq}). Ignorando y retransmitiendo...", "WARNING")
                        else:
                            log(f"[S] {res_pkt.type} seq={res_pkt.seq} -> RECHAZADO. Reintentando...", "WARNING")
                        attemps += 1

                except socket.timeout:
                    log(f"[S] Tiempo de espera expirado para id={pkt.pkt_id}. Retransmitiendo...", "WARNING")
                    attemps += 1

    def _check_success(self, proto, res):
        """Defines what constitutes 'success' for each protocol."""
        if proto == "2.0":
            return res.type == "ACK"
            
        if proto in ["2.1", "2.2", "3.0"]:
            return res.type == "ACK" and res.seq == self.current_seq
            
        return False

    def close(self):
        log(f"Todos los mensajes fueron enviados y recibidos correctamente.")
        log(f"Terminando conexión.")

        self.sock.close()

# Example execution
if __name__ == "__main__":
    client = RDTClient("127.0.0.1", 8080, rdt_version="3.0", timeout=2, p_ack_drop=0.1)
    client.connect()
    
    mensajes = ["Este es un test", "Laboratorio RDT", "Finalizar"]
    client.rdt_send(mensajes)

    client.close()
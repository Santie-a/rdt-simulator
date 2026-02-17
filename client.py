import socket
import random
from datetime import datetime
from packet import Packet

def ts():
    return datetime.now().strftime("%M:%S.%f")

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
        # Do not set a global timeout here; timeout is applied only for rdt 3.0 per-send
        print(f"[{ts()}] [*] Conectado a {self.server_address}")
        print(f"[{ts()}] [*] Configurado con P(drop ACK/NACK)={self.p_ack_drop} y timeout={self.timeout}s (Para RDT 3.0)")

    def rdt_send(self, data_list):
        """
        Envía una lista de mensajes siguiendo las reglas del protocolo indicado.
        """
        for message in data_list:
            entregado = False
            intentos = 1
            
            while not entregado:
                # 1. Construir
                pkt = Packet("DATA", self.current_seq, self.global_pkt_id, message)
                
                # 2. Enviar y registrar traza (Requerido por informe)
                print(f"\n[{ts()}] ===== TX PKT id={pkt.pkt_id} seq={pkt.seq} =====")
                print(f"[{ts()}] [S] SEND {pkt.encode()} (Intento {intentos})")
                self.sock.send(pkt.encode().encode())

                try:
                    # 3. Esperar respuesta
                    # Apply timeout only for RDT 3.0 (where packet loss is modeled)
                    if self.rdt_version == "3.0" and self.timeout:
                        self.sock.settimeout(self.timeout)
                    else:
                        # blocking mode
                        self.sock.settimeout(None)

                    # Simulate ACK/NACK loss at the client side: cause a timeout
                    if self.rdt_version in ["2.1", "2.2", "3.0"] and random.random() < self.p_ack_drop:
                        print(f"\n[{ts()}] [SIMULACIÓN]: ACK/NACK perdido")
                        intentos += 1
                        continue

                    raw_res = self.sock.recv(1024).decode()
                    res_pkt = Packet.decode(raw_res)

                    if not res_pkt:
                        print(f"[{ts()}] [S] RECV Corrupt ACK/NACK -> Ignorar/Retransmitir")
                        intentos += 1
                        continue

                    # 4. Lógica de Decisión según Protocolo
                    if self._check_success(self.rdt_version, res_pkt):
                        print(f"[{ts()}] [S] RECV {res_pkt.tipo} seq={res_pkt.seq} -> OK.")
                        entregado = True
                        # Alternar secuencia para 2.1, 2.2 y 3.0
                        if self.rdt_version != "2.0":
                            self.current_seq = 1 - self.current_seq
                        self.global_pkt_id += 1
                    else:
                        # Distinguish corruption (NACK), duplicate/old ACKs, or generic rejection
                        if res_pkt.tipo == "NACK":
                            print(f"[{ts()}] [S] RECV NACK -> Receptor indica corrupción. Retransmitiendo...")
                        elif res_pkt.tipo == "ACK" and res_pkt.seq != self.current_seq:
                            print(f"[{ts()}] [S] RECV ACK seq={res_pkt.seq} -> DUPLICATE/OLD ACK (expected {self.current_seq}). Ignorando y retransmitiendo...")
                        else:
                            print(f"[{ts()}] [S] RECV {res_pkt.tipo} seq={res_pkt.seq} -> RECHAZADO. Reintentando...")
                        intentos += 1

                except socket.timeout:
                    print(f"[{ts()}] [S] TIMEOUT expirado para id={pkt.pkt_id}. Retransmitiendo...")
                    intentos += 1

    def _check_success(self, proto, res):
        """Define qué es un 'éxito' para cada protocolo"""
        if proto == "2.0":
            return res.tipo == "ACK"
            
        if proto in ["2.1", "2.2", "3.0"]:
            return res.tipo == "ACK" and res.seq == self.current_seq
            
        return False

    def close(self):
        print(f"\n[{ts()}] Todos los mensajes fueron enviados y recibidos correctamente.")
        print(f"[{ts()}] Terminando conexión.")

        self.sock.close()

# Ejemplo de ejecución
if __name__ == "__main__":
    client = RDTClient("127.0.0.1", 8080, rdt_version="2.1", timeout=2, p_ack_drop=0.1)
    client.connect()
    
    mensajes = ["Este es un test", "Laboratorio RDT"]
    client.rdt_send(mensajes)

    client.close()
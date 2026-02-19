import socket
import random
from datetime import datetime
from packet import Packet


def log(message, level="INFO"):
    timestamp = datetime.now().strftime("%M:%S.%f")[:-3]
    print(f"[{timestamp}] [{level}] {message}")


class RDTClient:
    def __init__(self, server_ip, port, rdt_version="3.0", timeout=None, p_ack_drop=0.0):
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
        log(f"Configuración: RDT {self.rdt_version}, timeout={self.timeout}, P(ACK_loss)={self.p_ack_drop}")

    def rdt_send(self, data_list):

        for message in data_list:
            delivered = False
            attempts = 1
            last_reason = None

            while not delivered:

                # Determinar tipo de envío
                if attempts == 1:
                    pkt_type = "DATA"
                else:
                    pkt_type = f"RETRANSMISSION_{last_reason}"

                # Construir paquete
                pkt = Packet(pkt_type, self.current_seq, self.global_pkt_id, message, attempt=attempts)

                log(f"===== TX PKT id={pkt.pkt_id} seq={pkt.seq} type={pkt.type} =====")
                log(f"[S] Enviando: {pkt.encode()} (Intento {attempts})")

                self.sock.send(pkt.encode().encode())

                try:
                    # Configurar timeout si aplica
                    if self.rdt_version in ["2.1", "2.2", "3.0"] and self.timeout:
                        self.sock.settimeout(self.timeout)
                    else:
                        self.sock.settimeout(None)

                    raw_res = self.sock.recv(1024).decode()
                    res_pkt = Packet.decode(raw_res)

                    # Simular pérdida de ACK/NACK
                    if self.rdt_version in ["2.1", "2.2", "3.0"] and random.random() < self.p_ack_drop:
                        log("[SIMULACIÓN] ACK/NACK perdido", "WARNING")
                        last_reason = "ACK_LOST"
                        attempts += 1
                        continue

                    if not res_pkt:
                        log("[S] ACK/NACK corrupto", "WARNING")
                        last_reason = "CORRUPT"
                        attempts += 1
                        continue

                    log(f"===== RX PKT id={res_pkt.pkt_id} seq={res_pkt.seq} type={res_pkt.type} =====")

                    # Verificar éxito
                    if self._check_success(res_pkt):
                        log("[S] ACK correcto recibido -> OK")
                        delivered = True

                        if self.rdt_version != "2.0":
                            self.current_seq = 1 - self.current_seq

                        self.global_pkt_id += 1

                    else:
                        # Identificar causa
                        if res_pkt.type == "NACK":
                            last_reason = "NACK"
                            log("[S] NACK recibido -> Retransmitiendo", "WARNING")

                        elif res_pkt.type == "ACK" and res_pkt.seq != self.current_seq:
                            last_reason = "INCORRECT_SEQ"
                            log("[S] ACK Incorrect -> Retransmitiendo", "WARNING")

                        else:
                            last_reason = "REJECT"
                            log("[S] Respuesta inválida -> Retransmitiendo", "WARNING")

                        attempts += 1

                except socket.timeout:
                    log("[S] TIMEOUT esperando ACK", "WARNING")
                    last_reason = "TIMEOUT"
                    attempts += 1

    def _check_success(self, res_pkt):

        if self.rdt_version == "2.0":
            return res_pkt.type == "ACK"

        if self.rdt_version in ["2.1", "2.2", "3.0"]:
            return res_pkt.type == "ACK" and res_pkt.seq == self.current_seq

        return False

    def close(self):
        log("Todos los mensajes fueron enviados correctamente.")
        log("Cerrando conexión.")
        self.sock.close()

if __name__ == "__main__":

    client = RDTClient(
        server_ip="127.0.0.1",
        port=8080,
        rdt_version="2.2",
        timeout=2,
        p_ack_drop=0.2
    )

    client.connect()

    mensajes = [
        "Este es un test",
        "Laboratorio RDT",
        "Finalizar"
    ]

    client.rdt_send(mensajes)
    client.close()

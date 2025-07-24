import socket
import struct
import time
from protos import messages_pb2

class Mulicast:
    def __init__(self):
        self.MCAST_GROUP = '224.1.1.1'
        self.MCAST_PORT = 5007
        self.discovered_devices = {} 
        self.broker_port = 5672
        self.topic = "sensores"
        device_info_payload = messages_pb2.DeviceInfo()
        device_info_payload.broker_port=self.broker_port
        device_info_payload.topic=self.topic
        self.discovery_request_msg = messages_pb2.SmartCityMessage(devices =device_info_payload)
        
    def getDevices(self):
        return list(self.discovered_devices.values())

    def add_or_update_device(self, device_info, addr):
        if not isinstance(device_info, messages_pb2.DeviceInfo):
            print(f"[Multicast] Erro: Tentativa de adicionar um objeto que não é DeviceInfo.")
            return
            
        print(f"[Multicast] Dispositivo '{device_info.device_id}' adicionado/atualizado da fonte {addr}.")
        self.discovered_devices[device_info.device_id] = (device_info, addr)

    def Server(self):
        """
        Envia 'pings' de descoberta periodicamente. A resposta é tratada
        pelo servidor UDP principal do Gateway.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        
        print(f"[Multicast] Iniciando envio de pings de descoberta para {self.MCAST_GROUP}:{self.MCAST_PORT}")

        while True:
            try:
                sock.sendto(self.discovery_request_msg.SerializeToString(), (self.MCAST_GROUP, self.MCAST_PORT))
                time.sleep(10)
            except Exception as e:
                print(f"[Multicast] Erro ao enviar ping de descoberta: {e}")
                time.sleep(10)
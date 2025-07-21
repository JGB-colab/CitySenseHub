from concurrent import futures
import time

import grpc
import messages_pb2
import messages_pb2_grpc

class messageService(messages_pb2_grpc.SmartCityServicer):
    def __init__(self):
        self.discovered_devices = {}

    def falsetrue(self, value):
        return value.lower() == 'true'

    def findDevice(self, tipo_dispositivo):
        for device_id, (device_info, addr) in self.discovered_devices.items():
            if device_info.device_type == tipo_dispositivo:
                return (device_info, addr)
        return None

    def send_command_to_device(self, device_info, ligar=None, consultar=None):
        # Simula o envio de comando para o dispositivo
        if ligar is not None:
            return f"Dispositivo {device_info.device_id} {'ligado' if ligar else 'desligado'}."
        elif consultar is not None:
            return f"Estado do dispositivo {device_info.device_id} consultado."
        return "Comando não reconhecido."

    def listDevices(self):
        return "\n".join([f"{device_id}: {info.device_type}" for device_id, (info, _) in self.discovered_devices.items()])
    
    def StateDevice(self, request, context):
        print('entrou aqui mermao')
        return messages_pb2.Query(status=False)   
    
def server():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    messages_pb2_grpc.add_SmartCityServicer_to_server(messageService(), server)
    server.add_insecure_port('localhost:50051')
    server.start()
    server.wait_for_termination()
    
if __name__ == '__main__':
    print("Iniciando o servidor gRPC...")
    server()    
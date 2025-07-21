import messages_pb2_grpc
import messages_pb2
import grpc

import time
import json
def get_client_stream_requests():
    while True:
        name = input('Coloque seu nome: ')
        if name == "":
            break
        hello_request = name
        print(f'Hello {hello_request}')
        time.sleep(1)

def handle_grpc_client_command(self, request):

        port = request['port']
        main_command = request['type_command']

        try:
            with grpc.insecure_channel(f'localhost:{port}') as channel:
                stub = messages_pb2_grpc.SmartCityStub(channel)
                command_str = request
                parts = command_str.split(';')
                main_command = ''
                               
                if main_command == 'LIGAR_DISPOSITIVO' and len(parts) == 3:
                    tipo_dispositivo = int(parts[1])
                    ligar = self.falsetrue(parts[2])
                    device_info_tuple = self.findDevice(tipo_dispositivo)
                    if device_info_tuple:
                        resposta_do_dispositivo = self.send_command_to_device(device_info_tuple[0], ligar=ligar)
                        resposta_para_cliente = resposta_do_dispositivo
                    else:
                        resposta_para_cliente = f"ERRO: Nenhum dispositivo do tipo {tipo_dispositivo} encontrado."
                
                elif main_command == 'CONSULTAR_DISPOSITIVO' and len(parts) == 3:
                    tipo_dispositivo = int(parts[1])
                    consultar = self.falsetrue(parts[2])
                    device_info_tuple = self.findDevice(tipo_dispositivo)
                    if device_info_tuple:
                        resposta_do_dispositivo = self.send_command_to_device(device_info_tuple[0], consultar=consultar)
                        resposta_para_cliente = resposta_do_dispositivo
                    else:
                        resposta_para_cliente = f"ERRO: Nenhum dispositivo do tipo {tipo_dispositivo} encontrado."

                elif main_command == "LISTAR_DISPOSITIVOS":
                    resposta_para_cliente = self.listDevices()
                
                else:
                    resposta_para_cliente = "ERRO: Comando desconhecido ou formato inválido."

                if resposta_para_cliente is None:
                    resposta_para_cliente = f"ERRO: Falha na comunicação com o dispositivo."

        except Exception as e:
            print(f"[Gateway] Erro ao processar cliente: {e}")                       
class Grpc():
     def __init__(self):
         ...
           

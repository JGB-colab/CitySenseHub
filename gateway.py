import socket
import threading
import time
import jwt
import os
import grpc
from protocols import tcp, udp, multicast
from flask import Flask, jsonify, request
from flask_restful import Api, Resource
from datetime import datetime, timedelta
from functools import wraps
from sys import path
c = os.path.abspath(os.curdir) + r'\protos'
path.insert(0, c)
import protos.messages_pb2 as messages_pb2
import protos.messages_pb2_grpc as messages_pb2_grpc
import sys
c_pubsub = os.path.abspath(os.curdir) + r'\protocols'
sys.path.insert(0, c_pubsub)
import pubsub

app = Flask(__name__)
api = Api(app)

##### Métodos de Conexão Rest Gateway #####
SECRET_KEY = os.getenv("SECRET_KEY", "ADMIN")
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return {"message": "Token não fornecido"}, 401 # JSON na resposta

        parts = auth_header.split()
        if parts[0].lower() != "bearer" or len(parts) != 2:
            return {"message": "Cabeçalho de autorização mal formatado"}, 401 # JSON na resposta
        
        token = parts[1]
        
        try:
            decoded = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return {"message": "Token expirado! Conecte novamente"}, 401 # JSON na resposta
        except jwt.InvalidTokenError:
            return {"message": "Token inválido"}, 401 # JSON na resposta
        
        return f(*args, **kwargs)
    return decorated


class Gateway:
    """
    Componente central do sistema. Gerencia a descoberta de dispositivos,
    roteia comandos de clientes e recebe dados de sensores.
    """
    def __init__(self):
        self.udpServer = udp.UDP('0.0.0.0', 5008) # Escuta em todas as interfaces.
        self.multicastServer = multicast.Mulicast()
        self.pubsub = pubsub.Broker()
        self.discovered_devices = {} # Dicionário para armazenar dispositivos online.
            
    def start(self):
        """Inicia todos os serviços do gateway em threads separadas."""
        print("Gateway iniciando todos os serviços...")

        # Passa a função de tratamento de pacotes para o servidor UDP.
        udp_thread = threading.Thread(target=self.udpServer.Server, args=(self.handle_udp_packet,), daemon=True)
        discovery_thread = threading.Thread(target=self.multicastServer.Server, daemon=True)
        broker_thread = threading.Thread(target=self.pubsub.Sub, daemon=True)
        udp_thread.start()
        discovery_thread.start()
        broker_thread.start()
        
        print("Gateway está online. Pressione Ctrl+C para sair.")
        try:
            while True:
                time.sleep(10)
        except KeyboardInterrupt:
            print("\nEncerrando o Gateway...")

    def handle_udp_packet(self, data, addr):
        """Processa pacotes UDP recebidos (anúncios ou dados de sensores)."""
        try:
            message = messages_pb2.SmartCityMessage()
            message.ParseFromString(data)
            
            if message.HasField("devices"):
                device_info = message.devices
                self.discovered_devices[device_info.device_id] = (device_info, addr)
                print(f"[Gateway] Dispositivo '{device_info.device_id}' adicionado/atualizado.")

            elif message.HasField("sensor_data"):
                sensor_data = message.sensor_data
                print(f"[Gateway UDP] Dados de sensor de {sensor_data.device_id}: {sensor_data.value} {sensor_data.unit}")
        
        except Exception as e:
            print(f"[Gateway UDP] Pacote de {addr} não pôde ser decodificado: {e}")

    def handle_grpc_client_command(self, target_device_info, main_command, request_data):

        device_id = target_device_info.device_id
        device_ip = target_device_info.ip_address
        device_port = target_device_info.port


        try:
            with grpc.insecure_channel(f'{device_ip}:{device_port}') as channel:
                stub = messages_pb2_grpc.SmartCityStub(channel)
                                    
                if main_command == 'LIGAR_DISPOSITIVO':
                    ligar = request_data.get('ligar')
                    command_payload = messages_pb2.Command(state=ligar)
                    
                    # *** MUDANÇA AQUI: Usando ChangeStateRequest ***
                    grpc_request_message = messages_pb2.ChangeStateRequest(
                        device_id=device_id,
                        command=command_payload
                    )

                    print(f"[Gateway] Enviando ChangeState para {device_id} (estado: {ligar})...")
                    response_from_device = stub.ChangeState(grpc_request_message)
                    return {"message": f"Comando ChangeState para {device_id} enviado. Status: {'LIGADO' if response_from_device.status else 'DESLIGADO'}"}, 200

                elif main_command == 'CONSULTAR_DISPOSITIVO':
                    grpc_request_message = messages_pb2.StateDeviceRequest(
                        device_id=device_id
                    )
                    print(f"[Gateway] Enviando StateDevice para {device_id}...")
                    response_from_device = stub.StateDevice(grpc_request_message)
                    return {"message": f"Estado de {device_id}: {'LIGADO' if response_from_device.status else 'DESLIGADO'}"}, 200

                else:
                    return {"message": "Comando gRPC desconhecido."}, 400
                
        except grpc.RpcError as e:
            print(f"[Gateway] Erro gRPC ao comunicar com {device_id}: {e.code().name} - {e.details()}")
            return {"message": f"Erro de comunicação gRPC com o dispositivo {device_id}: {e.details()}"}, 500
        except Exception as e:
            print(f"[Gateway] Erro inesperado ao processar comando gRPC: {e}")
            return {"message": f"Erro interno ao enviar comando: {e}"}, 500

        
    def listDevices(self):
        """Retorna uma lista de dicionários com IDs e tipos de dispositivos online."""
        if not self.discovered_devices:
            return []

        device_list = []
        for device_id, (device_info_obj, _) in self.discovered_devices.items():
            device_list.append({
                "id": device_id,
                "type": messages_pb2.DeviceType.Name(device_info_obj.type),
                "ip": device_info_obj.ip_address,
                "port": device_info_obj.port,
                "is_actuator": device_info_obj.is_actuator
            })
        print(device_list)
        return device_list # Retorna a lista de dicionários Python

    
    def findDevice(self, tipo_int):
        """Busca o primeiro dispositivo de um tipo específico na lista de descobertos."""
        for device_info_obj, addr in self.discovered_devices.values():
            if device_info_obj.type == tipo_int:
                print(f"Dispositivo do tipo '{messages_pb2.DeviceType.Name(tipo_int)}' encontrado: {device_info_obj.device_id}")
                return (device_info_obj, addr)
        
        print(f"Nenhum dispositivo do tipo '{messages_pb2.DeviceType.Name(tipo_int)}' foi encontrado.")
        return None
        
    def falsetrue(self, valor):
        """Converte uma string 'true'/'false' para um booleano."""
        return valor.lower() == 'true'
    
global_gateway_instance = Gateway() 


class AuthResource(Resource):
     def post(self):
        data = request.get_json()
        if not data:
            return jsonify(message="Dados de Login não fornecidos"), 400  
        if "username" not in data or "password" not in data:
            return jsonify(message="Campos 'username' e 'password' são obrigatórios!"), 400
        if data["username"] == "admin" and data["password"] == "123":
            token = jwt.encode(
                {
                    'user': data['username'],
                    'exp': datetime.utcnow() + timedelta(minutes=30)
                },
                SECRET_KEY,
                algorithm='HS256'
            )
            return jsonify(token=token)
        return jsonify(message="Credenciais inválidas"), 401
      

class ProtectedResource(Resource):
    def get(self):
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return jsonify(message="Token não fornecido"), 401
        parts = auth_header.split()
        if parts[0].lower() != "bearer" or len(parts) != 2:
            return jsonify(message="Cabeçalho mal formatado"), 401
        token = parts[1]
        try:
            decoded = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            return jsonify(message="Cliente Conectado", user=decoded['user'])
        except jwt.ExpiredSignatureError:
            return jsonify(message="Token expirado! Conecte novamente"), 401
        except jwt.InvalidTokenError:
            return jsonify(message="Token inválido"), 401
        
class ApiGatewayConsultas(Resource):
    
    # define objeto gateway para puxar dispositivos
    def __init__(self):
        super().__init__()
        self.gateway = global_gateway_instance

    ### ROTA CONSULTAS DISPOSITIVOS ###
    # rota de consultas de dispostivos list
    
    @token_required
    def get(self,id):
        
        if id==0:
            return self.gateway.listDevices(), 200
        
        device_info_tuple = self.gateway.findDevice(id) 
    
        if device_info_tuple:
            device_info_obj = device_info_tuple[0] # Este é o objeto DeviceInfo Protobuf

            response_data, status_code = self.gateway.handle_grpc_client_command(
                target_device_info=device_info_obj,
                main_command='CONSULTAR_DISPOSITIVO',
                request_data={}
            )
            print(response_data)
            return response_data, status_code # CORRIGIDO: Retorne a tupla diretamente
        else:
            return {"message": f"Dispositivo do tipo {messages_pb2.DeviceType.Name(id)} não encontrado ou offline."}, 404

    
class ApiGatewayChanges(Resource):
    def __init__(self):
        super().__init__()
        self.gateway = global_gateway_instance
    @token_required
    def post(self, id): # 'id' aqui é o DeviceType int (ex: 1 para LIGHT_POST)
        request_data = request.get_json() # Pega o corpo JSON da requisição POST
        if not request_data:
            return {"message": "Corpo da requisição JSON ausente ou vazio."}, 400

        # 1. Encontrar o dispositivo pelo 'id' (tipo de dispositivo)
        device_info_tuple = self.gateway.findDevice(id) 

        if device_info_tuple:
            device_info_obj = device_info_tuple[0] # Este é o objeto DeviceInfo Protobuf

            # 2. Determinar o comando principal
            main_command = request_data.get('type_command')

            if main_command == 'LIGAR_DISPOSITIVO':
                response_data, status_code = self.gateway.handle_grpc_client_command(
                    target_device_info=device_info_obj,
                    main_command='LIGAR_DISPOSITIVO',
                    request_data=request_data 
                )
                return response_data, status_code # CORRIGIDO: Retorne a tupla diretamente
            else:
                change_definition_img = request_data.get('img')
                if change_definition_img is not None:
                    query_qlty_image = request.args.get('img', default= '720 px', type=str) # args.get é para query params, não body
                    return {"message": f"Comando de mudança para {id} com qlty_image {query_qlty_image} recebido. (Não gRPC)"}, 200
                else:
                    return {"message": "Nenhum comando reconhecido ou dado de 'img' fornecido no body."}, 400
        else:
            return {"message": f"Dispositivo do tipo {messages_pb2.DeviceType.Name(id)} não encontrado ou offline."}, 404

api.add_resource(AuthResource, '/login') # Rota de login
api.add_resource(ProtectedResource, '/protected') # Rota protegida de exemplo        
api.add_resource(ApiGatewayConsultas , '/consultas', '/consultas/<int:id>')
api.add_resource(ApiGatewayChanges , '/dispositivos', '/dispositivos/<int:id>')


def run_flask_app():
    print("Iniciando servidor Flask na thread...")
    app.run(port=5000, debug=False, use_reloader=False) 

if __name__ == "__main__":
    network_services_thread = threading.Thread(target=global_gateway_instance.start, daemon=True)
    network_services_thread.start()

    flask_thread = threading.Thread(target=run_flask_app)
    flask_thread.daemon = True 
    flask_thread.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nEncerrando a aplicação por KeyboardInterrupt...")
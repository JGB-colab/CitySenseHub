import os
import sys
from concurrent import futures

c = os.path.abspath(os.curdir) + r'\protos'
sys.path.insert(0, c)
c_pubsub = os.path.abspath(os.curdir) + r'\protocols'
sys.path.insert(0, c_pubsub)
import socket
import struct
import threading
import time
import uuid
import grpc
import messages_pb2
import messages_pb2_grpc
import pubsub

# --- Configurações de Rede (Comuns a todos) ---
MULTICAST_GROUP = '224.1.1.1'
MULTICAST_PORT = 5007

class messageService(messages_pb2_grpc.SmartCityServicer):
    def __init__(self, device_id_param, is_actuator_param):
        self.device_id = device_id_param
        self.is_actuator = is_actuator_param
        self.current_state = False
        print(f"[{self.device_id}] Servicer GRPC inicializado. Atuador: {self.is_actuator}, Estado inicial: {self.current_state}")

    def StateDevice(self, request, context):
        """Implementa o método gRPC para consultar o estado deste dispositivo."""
        print(f"[{self.device_id}] Requisição StateDevice recebida.")
        
        requested_device_id = request.device_id 
        
        if requested_device_id == self.device_id:
            print(f"[{self.device_id}] Respondendo estado: {'LIGADO' if self.current_state else 'DESLIGADO'}")
            return messages_pb2.Query(status=self.current_state)
        else:
            context.set_details(f"Requisição StateDevice para ID de dispositivo incorreto: {requested_device_id}")
            context.set_code(grpc.StatusCode.NOT_FOUND)
            return messages_pb2.Query(status=False)

    def ChangeState(self, request, context):
        """Implementa o método gRPC para mudar o estado deste dispositivo."""
        print(f"[{self.device_id}] Requisição ChangeState recebida.")

        if not self.is_actuator:
            context.set_details(f"[{self.device_id}] Não é um atuador, não pode mudar estado.")
            context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
            return messages_pb2.Query(status=False)

        requested_device_id = request.device_id 
        new_state = request.command.state 

        if requested_device_id == self.device_id:
            self.current_state = new_state
            print(f"[{self.device_id}] Estado alterado para: {'LIGADO' if self.current_state else 'DESLIGADO'}")
            return messages_pb2.Query(status=self.current_state)
        else:
            context.set_details(f"Requisição ChangeState para ID de dispositivo incorreto: {requested_device_id}")
            context.set_code(grpc.StatusCode.NOT_FOUND)
            return messages_pb2.Query(status=False)
      
class Dispositivos:
    """Classe base para todos os dispositivos da cidade inteligente."""

    def __init__(self, tipo):
        self.device_id = f"{tipo.lower().replace(' ', '_')}_{str(uuid.uuid4())[:4]}"
        self.tipo = tipo
        self.ip = '127.0.0.1'
        self.port = 0
        self.is_actuator = False
        self.pub = pubsub.Broker()
        self.broker_port =  None

    def __str__(self):
        return f"ID: {self.device_id}, Tipo: {self.tipo}, Endereço: {self.ip}:{self.port}, Atuador: {self.is_actuator}"

    def iniciar(self):
        print(f"Iniciando dispositivo: {self.device_id}")

        grpc_server_thread = threading.Thread(target=self.start_grpc_server, args=(self.device_id, self.is_actuator,), daemon=True)
        grpc_server_thread.start()

        time.sleep(1)

        discovery_thread = threading.Thread(target=self.listen_for_discovery, daemon=True)
        discovery_thread.start()

        print(f"{self.device_id} iniciado. gRPC em {self.ip}:{self.port}. Pressione Ctrl+C para sair.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print(f"\nDesligando {self.device_id}.")

    def start_grpc_server(self, device_id, is_actuator):
        """Lógica do servidor GRPC que fica aguardando conexões do Gateway."""
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        messages_pb2_grpc.add_SmartCityServicer_to_server(
            messageService(device_id, is_actuator), server)
        
        self.port = server.add_insecure_port('[::]:0')
        server.start()
        print(f"[{self.device_id}] Servidor GRPC escutando em {self.ip}:{self.port}")
        server.wait_for_termination()
        print(f"[{self.device_id}] Servidor GRPC encerrado.")


    def listen_for_discovery(self):
        multicast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        multicast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        multicast_socket.bind(('', MULTICAST_PORT))

        mreq = struct.pack("4sl", socket.inet_aton(MULTICAST_GROUP), socket.INADDR_ANY)
        multicast_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        print(f"[{self.device_id}] Aguardando descoberta em {MULTICAST_GROUP}:{MULTICAST_PORT}")

        while True:
            try:
                data, address = multicast_socket.recvfrom(1024)
                smart_city_message = messages_pb2.SmartCityMessage()
                smart_city_message.ParseFromString(data)
                if smart_city_message.HasField('devices'):
                    device_info_received = smart_city_message.devices
                    self.broker_port = device_info_received.broker_port
                    self.topic = device_info_received.topic
                    print(f"[{self.device_id}] Mensagem de Descoberta Recebida de {address}. Porta do Broker: {self.broker_port}")

                self.send_announcement(address)
            except Exception as e:
                print(f"[{self.device_id}] Erro no listener de descoberta: {e}")


    def send_announcement(self, gateway_address ):
        """Envia a mensagem de anúncio (Protocol Buffers) para o Gateway."""
        device_info_payload = messages_pb2.DeviceInfo()
        
        proto_device_type = getattr(messages_pb2.DeviceType, self.tipo.upper(), messages_pb2.DeviceType.UNKNOWN)

        device_info_payload.device_id = self.device_id
        device_info_payload.type = proto_device_type
        device_info_payload.ip_address = self.ip
        device_info_payload.port = self.port
        device_info_payload.is_actuator = self.is_actuator

        response_message = messages_pb2.SmartCityMessage(devices=device_info_payload)

        gateway_ip = gateway_address[0]
        self.gateway_data_port = 5008
         
        
        response_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        response_socket.sendto(response_message.SerializeToString(), (gateway_ip, self.gateway_data_port))
        response_socket.close()
        print(f"[{self.device_id}] Anúncio enviado para {gateway_ip}:{self.gateway_data_port} (Porta gRPC: {self.port}).")


class Atuador(Dispositivos):
    def __init__(self, tipo):
        super().__init__(tipo=tipo)
        self.is_actuator = True
        self._running = True # Flag


class Continuos(Dispositivos):
    def __init__(self, tipo, data_unit=""):
        super().__init__(tipo=tipo)
        self.is_actuator = False
        self.data_unit = data_unit
        self._running = True # Flag

    def iniciar(self):
        print(f"Iniciando sensor: {self.device_id}")

        discovery_thread = threading.Thread(target=self.listen_for_discovery, daemon=True)
        discovery_thread.start()

        data_thread = threading.Thread(target=self.start_sending_data, daemon=True)
        data_thread.start()
        
        grpc_server_thread = threading.Thread(target=self.start_grpc_server, args=(self.device_id, self.is_actuator,), daemon=True)
        grpc_server_thread.start()
        time.sleep(1)

        print(f"{self.device_id} iniciado. gRPC em {self.ip}:{self.port}. Pressione Ctrl+C para sair.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print(f"\nDesligando {self.device_id}.")

    def start_sending_data(self):
        import random
        print(f"[{self.device_id}] Enviando dados de sensor para a Fila")

        while True:
            try:
                if self.tipo == "TEMPERATURE_SENSOR":
                    leitura = round(random.uniform(18.0, 35.0), 2)
                elif self.tipo == "AIR_QUALITY_SENSOR":
                    leitura = round(random.uniform(0.0, 100.0), 2)
                else:
                    leitura = round(random.uniform(0.0, 100.0), 2)

                '''sensor_payload = messages_pb2.SensorData(
                    device_id=self.device_id,
                    value=leitura,
                    unit=self.data_unit
                )'''
                #response_message = messages_pb2.SmartCityMessage(sensor_data=sensor_payload)
                if self.broker_port is None:
                    print('Ainda sem endereço do Broker')
                else:
                   self.pub.Pub(self.broker_port,self.topic, self.device_id, leitura, self.data_unit)
                time.sleep(15)
            except Exception as e:
                print(f"[{self.device_id}] Erro ao enviar dados de sensor: {e}")

    def parar(self):
        self._running = False

class GerenciarCidade:
    def iniciar_dispositivos_simulados(self, falha=False):
        """Cria e inicia múltiplos dispositivos em threads separadas."""
        
        # 💡 Lista de dispositivos, conforme o seu código original
        dispositivos_a_iniciar = [
            Atuador(tipo='LIGHT_POST'),
            Atuador(tipo='TRAFFIC_LIGHT'),
            Atuador(tipo='CAMERA'),
            Continuos(tipo='TEMPERATURE_SENSOR', data_unit="Celsius"),
            Continuos(tipo='AIR_QUALITY_SENSOR', data_unit="µg/m³")
        ]

        if falha:
            dispositivos_a_iniciar = [
                Atuador(tipo='LIGHT_POST'),
                Continuos(tipo='TEMPERATURE_SENSOR', data_unit="Celsius")
            ]

        threads = []
        print("Iniciando simulação da cidade inteligente...")

        # 🚀 Criar um evento para sinalizar que as threads devem parar
        stop_event = threading.Event()

        for dispositivo in dispositivos_a_iniciar:
            # 📌 Adaptar o método 'iniciar' dos dispositivos para aceitar o stop_event
            # Isso requer uma pequena mudança nas classes Atuador e Continuos para que 'iniciar'
            # receba o stop_event e use-o no seu loop de execução.
            # No entanto, a forma mais simples é fazer com que as threads chamem um método que
            # use a flag '_running' do próprio dispositivo.
            thread = threading.Thread(target=dispositivo.iniciar)
            
            # Daemon threads permitem que o programa principal termine mesmo que as threads ainda estejam rodando.
            # O KeyboardInterrupt no main thread vai encerrar o programa, e as daemon threads serão forçadas a parar.
            thread.daemon = True 
            
            threads.append(thread)
            thread.start()

        print(f"\n{len(dispositivos_a_iniciar)} dispositivos foram iniciados em threads separadas.")
        print("O gateway agora pode iniciar o processo de descoberta.")
        print("Pressione Ctrl+C neste terminal para parar a simulação.")

        try:
            # 🔄 Usar stop_event.wait() para manter o thread principal vivo,
            # mas responsivo ao KeyboardInterrupt.
            # O argumento é o timeout, para que possa verificar o estado periodicamente
            while not stop_event.is_set():
                time.sleep(0.5) # Pequeno sleep para evitar busy-waiting
            
        except KeyboardInterrupt:
            print("\n🚨 KeyboardInterrupt detectado! Encerrando simulação...")
            stop_event.set() # Sinaliza para as threads que elas devem parar (se não fossem daemon)
            
            # 🛑 Sinalizar explicitamente cada dispositivo para parar seus loops
            # Isso é importante para que as threads terminem "limpamente" se não forem daemon
            # ou para que os logs de encerramento sejam exibidos.
            for dispositivo in dispositivos_a_iniciar:
                dispositivo.parar() # Chama o método 'parar' que seta _running = False

            # ⏳ Pequeno delay para permitir que as threads terminem seus loops internos
            time.sleep(2) 

        finally:
            print("Simulação principal encerrada. ✅")


if __name__ == '__main__':
    print('[1] Cenário Normal [2] Cenário de Falha')
    entrada = input('Digite a opção que você deseja: ')
    if entrada == '1':
        try:
            GerenciarCidade().iniciar_dispositivos_simulados()
        except KeyboardInterrupt:
            # Este bloco KeyboardInterrupt no 'if __name__ == "__main__":'
            # só é acionado se o KeyboardInterrupt não for tratado dentro de iniciar_dispositivos_simulados().
            # Com as mudanças propostas, ele será tratado dentro da função.
            print('Programa principal encerrado devido a KeyboardInterrupt.')
    elif entrada == '2':
        try:
            GerenciarCidade().iniciar_dispositivos_simulados(falha=True)
        except KeyboardInterrupt:
            print('Programa principal encerrado devido a KeyboardInterrupt.')

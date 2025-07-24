import os
import sys
from concurrent import futures

c = os.path.abspath(os.curdir) + r'\protos'
c_pubsub = os.path.abspath(os.curdir) + r'\protocols'
sys.path.insert(0, c)
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
    def __init__(self, device_instance, pub, port,topic):
        self.device = device_instance
        self.pub = pub
        self.broker_port = port
        self.topic = topic 
        print(f"[{self.device.device_id}] Servicer GRPC inicializado. Atuador: {self.device.is_actuator}, Estado inicial: {self.device.current_state}")

    def StateDevice(self, request, context):
        """Implementa o método gRPC para consultar o estado do dispositivo real."""
        print(f"[{self.device.device_id}] Requisição StateDevice recebida.")
        
        if request.device_id == self.device.device_id:
            # CORREÇÃO: Lê o estado diretamente da instância do dispositivo.
            print(f"[{self.device.device_id}] Respondendo estado: {'LIGADO' if self.device.current_state else 'DESLIGADO'}")
            return messages_pb2.Query(status=self.device.current_state)
        else:
            context.set_details(f"Requisição StateDevice para ID de dispositivo incorreto: {request.device_id}")
            context.set_code(grpc.StatusCode.NOT_FOUND)
            return messages_pb2.Query(status=False)

    def ChangeState(self, request, context):
        """Implementa o método gRPC para mudar o estado do dispositivo real."""
        print(f"[{self.device.device_id}] Requisição ChangeState recebida.")

        if not self.device.is_actuator:
            context.set_details(f"[{self.device.device_id}] Não é um atuador, não pode mudar estado.")
            context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
            return messages_pb2.Query(status=False)

        if request.device_id == self.device.device_id:
            self.device.current_state = request.command.state
            print(f"[{self.device.device_id}] Estado do dispositivo alterado para: {'LIGADO' if self.device.current_state else 'DESLIGADO'}")
            return messages_pb2.Query(status=self.device.current_state)
        else:
            context.set_details(f"Requisição ChangeState para ID de dispositivo incorreto: {request.device_id}")
            context.set_code(grpc.StatusCode.NOT_FOUND)
            return messages_pb2.Query(status=False)
    
    def ChangeTime(self, request, context):
        """Implementa o método gRPC para mudar o tempo de envio de sensores contínuos."""
        print(f"[{self.device.device_id}] Requisição ChangeTime recebida.")

        if self.device.is_actuator:
            context.set_details(f"[{self.device.device_id}] É um atuador, não pode mudar tempo de envio.")
            context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
            return messages_pb2.Query(status=False)

        if request.device_id == self.device.device_id:
            print('Dispositivo: ',self.device)
            self.device.config_time_send = request.time.value
            self.pub.Pub(self.broker_port, self.topic, self.device.device_id, f'Mudança de tempo para {self.device.config_time_send} s', 'seg')
            print(f"[{self.device.device_id}] Intervalo de envio de dados alterado para: {self.device.config_time_send}s")
            
            return messages_pb2.Time(value=self.device.config_time_send)
        else:
            context.set_details(f"Requisição ChangeTime para ID de dispositivo incorreto: {request.device_id}")
            context.set_code(grpc.StatusCode.NOT_FOUND)
            return messages_pb2.Time(status=self.device.config_time_send)
      
class Dispositivos:
    """Classe base para todos os dispositivos da cidade inteligente."""

    def __init__(self, tipo):
        self.device_id = f"{tipo.lower().replace(' ', '_')}_{str(uuid.uuid4())[:4]}"
        self.tipo = tipo
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

            s.connect(("8.8.8.8", 80)) 
            self.ip = s.getsockname()[0]
            s.close()
        except Exception:
            self.ip = '127.0.0.1'
        self.port = 0
        self.is_actuator = False
        self.current_state = False 
        self.pub = pubsub.Broker()
        self.broker_port =  None
        self.topic = None
        self._running = True 

    def __str__(self):
        return f"ID: {self.device_id}, Tipo: {self.tipo}, Endereço: {self.ip}:{self.port}, Atuador: {self.is_actuator}, Estado: {self.current_state}"

    def iniciar(self):
        print(f"Iniciando dispositivo: {self.device_id}")

        grpc_server_thread = threading.Thread(target=self.start_grpc_server, daemon=True)
        grpc_server_thread.start()
        time.sleep(1) # Dá um tempo para o servidor gRPC iniciar e definir a porta.

        discovery_thread = threading.Thread(target=self.listen_for_discovery, daemon=True)
        discovery_thread.start()

        if not self.is_actuator:
            data_thread = threading.Thread(target=self.start_sending_data, daemon=True)
            data_thread.start()

        print(f"{self.device_id} iniciado. gRPC em {self.ip}:{self.port}. Pressione Ctrl+C para sair.")
        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            print(f"\nDesligando {self.device_id}.")
        finally:
            self.parar()


    def start_grpc_server(self):
        """Lógica do servidor GRPC que fica aguardando conexões do Gateway."""
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        
        messages_pb2_grpc.add_SmartCityServicer_to_server(
            messageService(self,self.pub,5672, 'sensores'), server)
        self.port = server.add_insecure_port('[::]:0')
        print(f"[{self.device_id}] Servidor GRPC escutando em {self.ip}:{self.port}")
        server.start()
        server.wait_for_termination()
        print(f"[{self.device_id}] Servidor GRPC encerrado.")


    def listen_for_discovery(self):
        multicast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        multicast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        multicast_socket.bind(('', MULTICAST_PORT))

        mreq = struct.pack("4sl", socket.inet_aton(MULTICAST_GROUP), socket.INADDR_ANY)
        multicast_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        print(f"[{self.device_id}] Aguardando descoberta em {MULTICAST_GROUP}:{MULTICAST_PORT}")

        while self._running:
            try:
                # Adicionado timeout para que o loop possa verificar self._running e encerrar graciosamente
                multicast_socket.settimeout(1.0)
                data, address = multicast_socket.recvfrom(1024)
                smart_city_message = messages_pb2.SmartCityMessage()
                smart_city_message.ParseFromString(data)
                if smart_city_message.HasField('devices'):
                    device_info_received = smart_city_message.devices
                    self.broker_port = device_info_received.broker_port
                    self.topic = device_info_received.topic
                    print(f"[{self.device_id}] Mensagem de Descoberta Recebida de {address}. Porta do Broker: {self.broker_port}")
                    self.send_announcement(address)
            except socket.timeout:
                continue # Simplesmente volta ao início do loop
            except Exception as e:
                if self._running:
                    print(f"[{self.device_id}] Erro no listener de descoberta: {e}")


    def send_announcement(self, gateway_address):
        """Envia a mensagem de anúncio (Protocol Buffers) para o Gateway."""
        if self.port == 0:
            print(f"[{self.device_id}] Aviso: Porta gRPC ainda não definida. Anúncio adiado.")
            return

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
         
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as response_socket:
            response_socket.sendto(response_message.SerializeToString(), (gateway_ip, self.gateway_data_port))
        
        print(f"[{self.device_id}] Anúncio enviado para {gateway_ip}:{self.gateway_data_port} (Porta gRPC: {self.port}).")

    def parar(self):
        print(f"[{self.device_id}] Iniciando procedimento de parada.")
        self._running = False


class Atuador(Dispositivos):
    def __init__(self, tipo):
        super().__init__(tipo=tipo)
        self.is_actuator = True

class Continuos(Dispositivos):
    def __init__(self, tipo, data_unit=""):
        super().__init__(tipo=tipo)
        self.is_actuator = False
        self.data_unit = data_unit
        self.config_time_send = 15 # Tempo de envio padrão

    # REMOVIDO: O método SetConfig não é mais necessário, pois o gRPC faz a alteração diretamente.

    def start_sending_data(self):
        import random
        print(f"[{self.device_id}] Thread de envio de dados iniciada.")

        # Espera até ter as informações do broker
        while self.broker_port is None and self._running:
            print(f'[{self.device_id}] Aguardando endereço do Broker...')
            time.sleep(2)
        
        if not self._running: return

        print(f"[{self.device_id}] Enviando dados de sensor para a Fila no tópico '{self.topic}'")
        
        while self._running:
            try:
                leitura = None
                if self.tipo == "TEMPERATURE_SENSOR":
                    leitura = round(random.uniform(18.0, 35.0), 2)
                elif self.tipo == "AIR_QUALITY_SENSOR":
                    leitura = round(random.uniform(0.0, 100.0), 2)
                elif self.tipo == "GPS":  
                    latitude = round(random.uniform(-3.8, -3.7), 6)
                    longitude = round(random.uniform(-38.6, -38.4), 6)
                    leitura = f"lat:{latitude},lon:{longitude}" # Enviando como string simples

                if leitura is not None:
                   self.pub.Pub(self.broker_port, self.topic, self.device_id, str(leitura), self.data_unit)

                time.sleep(self.config_time_send)
                
            except Exception as e:
                if self._running:
                    print(f"[{self.device_id}] Erro ao enviar dados de sensor: {e}")

class GerenciarCidade:
    def iniciar_dispositivos_simulados(self, falha=False):
        """Cria e inicia múltiplos dispositivos em threads separadas."""
        
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

        for dispositivo in dispositivos_a_iniciar:
            thread = threading.Thread(target=dispositivo.iniciar, daemon=True)
            threads.append(thread)
            thread.start()

        print(f"\n{len(dispositivos_a_iniciar)} dispositivos foram iniciados em threads separadas.")
        print("O gateway agora pode iniciar o processo de descoberta.")
        print("Pressione Ctrl+C neste terminal para parar a simulação.")

        try:
            for thread in threads:
                thread.join()
        except KeyboardInterrupt:
            print("\n🚨 KeyboardInterrupt detectado! Encerrando simulação...")
            for dispositivo in dispositivos_a_iniciar:
                dispositivo.parar()
            time.sleep(1) # Dá um tempo para as threads terminarem
        finally:
            print("Simulação principal encerrada. ✅")


if __name__ == '__main__':
    print('[1] Cenário Normal [2] Cenário de Falha')
    entrada = input('Digite a opção que você deseja: ')
    gerenciador = GerenciarCidade()
    if entrada == '1':
        gerenciador.iniciar_dispositivos_simulados(falha=False)
    elif entrada == '2':
        gerenciador.iniciar_dispositivos_simulados(falha=True)
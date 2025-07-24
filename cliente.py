import socket
from protos import messages_pb2 
import requests
import json
# O endereço público do Gateway - a única coisa que o cliente precisa saber.
GATEWAY_IP = '127.0.0.1'
GATEWAY_TCP_PORT = 5009
# --- Configurações da sua API ---
#BASE_URL = "http://127.0.0.1:5000" # Mude para a URL da sua API se for diferente

LOGIN_ENDPOINT = "/login"
PROTECTED_CONSULTAS_ENDPOINT = "/consultas"
PROTECTED_ADD_CONSULTA_ENDPOINT = "/consultas" # POST
PROTECTED_GENERIC_ENDPOINT = "/protected"

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "123"

def enviar_comando_para_gateway(comando, tipo= None, ligar = None, consultar = None):
    """
    Função que abre uma conexão, envia um comando e retorna a resposta.
    """
    if tipo is not None and ligar is None and consultar is None:
        comando = f"{comando};{tipo}"
    elif ligar is not None:
        comando = f"{comando};{tipo};{ligar}"
    elif consultar is not None:
        comando = f"{comando};{tipo};{consultar}"

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((GATEWAY_IP, GATEWAY_TCP_PORT))
            
            s.sendall(comando.encode('utf-8'))
            
            resposta = s.recv(4096)
            return resposta            
    except ConnectionRefusedError:
        return "ERRO: Não foi possível conectar ao Gateway. Ele está online?"
    except Exception as e:
        return f"ERRO: Ocorreu um erro inesperado: {e}"


class Cliente: 
    def __init__(self):
        self.base_url = 'http://localhost:5000'
        self.token = None

    def login(self, username, password):    

        login_url = f'{self.base_url}/login'
        headers = {'Content-Type': 'application/json'}
        payload = {'username': username, 'password': password}
        
       
        try:
            response = requests.post (login_url, json= payload,headers=headers)
            data =response.json()
            if 'token' in data:
                self.token = data['token']
                print(f"Login bem-sucedido! Token: {self.token}")
                return True
            else:
                print(f"Erro ao fazer login: {data.get('message', 'Erro desconhecido')}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"Erro de conexão: {e}")
            return False 

    def get_auth_headers(self):
        if not self.token:
            raise Exception("Token não disponível. Faça login primeiro.")
        return { 
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }      
    def get_protected_data(self, endpoint):
        try:
            headers = self.get_auth_headers()
            url = f'{self.base_url}{endpoint}'
            response = requests.get(url, headers=headers)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Erro ao acessar dados protegidos: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Status Code: {e.response.status_code}, Mensagem: {e.response.text}")    
            return None
    def post_protected_data(self, endpoint, data):
        """
        Faz uma requisição POST para uma rota protegida.
        """
        try:
            headers = self.get_auth_headers()
            url = f"{self.base_url}{endpoint}"
            response = requests.post(url, headers=headers, json=data)
            print('Post metodo: ',response)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Erro ao enviar dados protegidos para {endpoint}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Detalhes da resposta de erro: {e.response.text}")
            return None

def main():
    print('### LOGIN ###')  
    
    client = Cliente()

    # 1. Tentar fazer login
    if client.login(ADMIN_USERNAME, ADMIN_PASSWORD):
        print("\n--- Testando rota /protected ---")
        protected_info = client.get_protected_data(PROTECTED_GENERIC_ENDPOINT)
        if protected_info:
            print(json.dumps(protected_info, indent=2))
            print("### CONTROLE DA CIDADE INTELIGENTE ###")
            while True:
                print('''
            [1] Ligar/Desligar um dispositivo 
                    (1) Poste
                    (2) Semáforo
                    (3) Câmera
            [2] Consultar Estado dos Dispositivos        
            [3] Listar todos os dispositivos online
            [4] Mudar configuração de envio de tempo
                   (1) Temperatura
                   (2) Qualidade do Ar
                   (3) GPS              
            [x] Sair
            ''')
                tipo_map = {
                        '1': messages_pb2.DeviceType.LIGHT_POST,
                        '2': messages_pb2.DeviceType.TRAFFIC_LIGHT,
                        '3': messages_pb2.DeviceType.CAMERA,
                        '4': messages_pb2.DeviceType.TEMPERATURE_SENSOR,
                        '5': messages_pb2.DeviceType.AIR_QUALITY_SENSOR,
                        '6': messages_pb2.DeviceType.GPS,
                    }
              
                input_usuario = input('Digite a opção desejada: ').lower().strip()
                        
                if input_usuario == '1':
                    dispositivo = input('Selecione o tipo de dispositivo a ser ligado (1=Poste, 2=Camera, 3=Semaforo): ').lower().strip()
                    ligar = input(r'Ligar[1]\Desligar[0]: ').lower().strip()
                    
                    if ligar == '0':
                        ligar = False
                    else:
                        ligar = True

                    comando = 'LIGAR_DISPOSITIVO'
            
                    if dispositivo in tipo_map:
                        tipo = tipo_map[dispositivo]
                        print(f"Enviando comando para ligar o tipo: {messages_pb2.DeviceType.Name(tipo)}")
                        data = {
                            'ligar': ligar,
                            'type_command': comando,
                            'device_type': tipo
                        }
                        resposta_do_servidor = client.post_protected_data(f'/dispositivos/{tipo}',data)

                        print(f"Resposta do Gateway: {resposta_do_servidor}")

                    else:
                        print("Tipo de dispositivo inválido.")
                        
                elif input_usuario == '2': 
                    dispositivo = input('Selecione o dispositivo a ser consultado(1=Poste, 2=Camera, 3=Semaforo) : ').lower().strip()
                    comando = 'CONSULTAR_DISPOSITIVO'
                  
                    if dispositivo in tipo_map:
                        tipo = tipo_map[dispositivo]
                        print(f"Enviando comando para consultar estado  {messages_pb2.DeviceType.Name(tipo)}")
                        resposta_do_servidor = client.get_protected_data(f'/consultas/{tipo}')
                        #resposta_do_servidor = enviar_comando_para_gateway(comando, tipo, ligar =None, consultar = consultar)
                        print(f"Resposta do Gateway: {resposta_do_servidor}")
                    else:
                        print("Tipo de dispositivo inválido.")

                elif input_usuario == '3':
                    comando = "LISTAR_DISPOSITIVOS" 
                    print("\nSolicitando lista de dispositivos ao Gateway...")
                    try:
                        resposta_do_servidor = client.get_protected_data((f'/consultas/0'))
                        dispositivos_existentes = [d['id'] for d in resposta_do_servidor]
                        print("--- Resposta do Gateway ---")
                        print('\n'.join(dispositivos_existentes))
                        print("---------------------------\n")

                    except AttributeError as e:
                        print(e)
                        print('[Erro 500]Serviço de gateway não disponível! Por favor, tente mais tarde')    
                
                elif input_usuario == '4':
                    print("\nSolicitando lista de dispositivos ao Gateway...")
                    
                    dispositivo = input('Selecione o tipo de dispositivo a ser ligado (4=Temp, 5=Ar, 6=GPS):').lower().strip()
                    tempo = input(r'Defina o tempo de envio: ').lower().strip()
                    
                    comando = 'MUDAR_TEMPO'
                    try:
                        if dispositivo in tipo_map:
                            tipo = tipo_map[dispositivo]
                            print(f"Enviando comando para ligar o tipo: {messages_pb2.DeviceType.Name(tipo)}")
                            data = {
                                'tempo': tempo,
                                'type_command': comando,
                                'device_type': tipo
                            }
                            resposta_do_servidor = client.post_protected_data(f'/dispositivos/{tipo}',data)

                            print(f"Resposta do Gateway: {resposta_do_servidor}")

                    except AttributeError:
                        print('[Erro 500]Serviço de gateway não disponível! Por favor, tente mais tarde')    
                elif input_usuario == 'x':
                    break
    else:
        print("\nNão foi possível fazer login. Verifique suas credenciais ou o servidor da API.")





if __name__ == "__main__":      
    main()
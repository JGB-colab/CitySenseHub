import pika
import json
import time
import random

'''
Finalizei o protótipo da comunicação via Broker. Aqui está como vamos usar o RabbitMQ:

Broker: Vamos usar RabbitMQ rodando via Docker.
Padrão: A comunicação será via um Topic Exchange chamado smart_city_exchange.
Formato da Mensagem: Todas as mensagens dos sensores serão em JSON.

Para os Sensores:
Vocês devem publicar as mensagens no exchange smart_city_exchange.
Usem um tópico no formato sensores.<tipo_do_sensor>.<id_do_dispositivo> (ex: sensores.temperatura.sala01).
O arquivo publisher_exemplo.py vai ser a base de vocês.

Para o Gateway:
Tem que  criar uma fila e se inscrever (fazer o bind) no smart_city_exchange.
Use o padrão de inscrição sensores.# para receber mensagens de todos os sensores.
O arquivo subscriber_exemplo.py vai ser a base para receber as mensagens.
'''
# 1. Conecta ao servidor RabbitMQ (que está rodando via Docker)
connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

# 2. Garante que o exchange 'smart_city_exchange' do tipo 'topic' exista
channel.exchange_declare(exchange='smart_city_exchange', exchange_type='topic')

# 3. Tópico que será usado para publicar a mensagem. Formato: sensores.<tipo>.<id>
routing_key = 'sensores.temperatura.sala01'

# 4. Mensagem de exemplo em formato de dicionário Python
message = {
  "deviceId": "temp-sensor-sala-01",
  "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
  "value": round(random.uniform(20.0, 30.0), 2), # Gera um valor aleatório
  "unit": "Celsius"
}

# 5. Converte o dicionário para uma string JSON
message_body = json.dumps(message)

# 6. Publica a mensagem no exchange com o tópico especificado
channel.basic_publish(
    exchange='smart_city_exchange',
    routing_key=routing_key,
    body=message_body
)

print(f" [x] Enviado '{routing_key}': '{message_body}'")

# 7. Fecha a conexão
connection.close()

class Broker():

    def Pub(self, port ,topic, deviceId, value, unit): # vai rodar num thread
      # 1. Conecta ao servidor RabbitMQ
      connection = pika.BlockingConnection(pika.ConnectionParameters('localhost', port= port))
      channel = connection.channel()

      # 2. Garante que o exchange 'smart_city_exchange' do tipo 'topic' exista
      channel.exchange_declare(exchange='smart_city_exchange', exchange_type='topic')

      # 3. Tópico que será usado para publicar a mensagem. Formato: sensores.<tipo>.<id>

      routing_key = f'{topic}.{deviceId}' # o envio dos dados devem seguir esse padrão

      # 4. Mensagem de exemplo em formato de dicionário Python
      message = {
        "deviceId": deviceId,#"temp-sensor-sala-01",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "value": value, # Gera um valor aleatório
        "unit": unit
      }

      # 5. Converte o dicionário para uma string JSON
      message_body = json.dumps(message)

      # 6. Publica a mensagem no exchange com o tópico especificado
      channel.basic_publish(
          exchange='smart_city_exchange',
          routing_key=routing_key,
          body=message_body,
          properties=pika.BasicProperties(
                         delivery_mode = pika.DeliveryMode.Persistent
      ))

      print(f" [x] Enviado '{routing_key}': '{message_body}'")

      # 7. Fecha a conexão
      connection.close()
   
    def Sub(self):
      # 1. Conecta ao servidor RabbitMQ
      connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
      channel = connection.channel()

      # 2. Garante que o exchange 'smart_city_exchange' exista
      channel.exchange_declare(exchange='smart_city_exchange', exchange_type='topic')

      # 3. Cria uma fila exclusiva. O RabbitMQ vai dar um nome aleatório.
      # 'exclusive=True' significa que a fila será deletada quando a conexão for fechada.
      result = channel.queue_declare(queue='', exclusive=True, durable=True)
      queue_name = result.method.queue

      # 4. Tópico de inscrição. 'sensores.#' significa "receba todas as mensagens de todos os sensores"
      binding_key = 'sensores.#'

      # 5. Faz a ligação (binding) entre o exchange e a nossa fila, usando o tópico
      channel.queue_bind(exchange='smart_city_exchange', queue=queue_name, routing_key=binding_key)

      print(' [*] Aguardando por mensagens. Para sair, pressione CTRL+C')

      # 6. Função que será chamada sempre que uma mensagem for recebida
      def callback(ch, method, properties, body):
          # Converte o corpo da mensagem (que está em bytes) para um dicionário Python
          message = json.loads(body)
          print(f" [x] Recebido | Tópico: '{method.routing_key}' | Mensagem: '{message}'")
          #ch.basic_ack(delivery_tag = method.delivery_tag)

      # 7. Diz ao RabbitMQ que a função 'callback' deve consumir mensagens da nossa fila
      channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)

      # 8. Inicia o consumo de mensagens (loop infinito)
      channel.start_consuming()
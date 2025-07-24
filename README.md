# Sistema de Simulação de Cidade Inteligente

Este projeto implementa uma simulação de uma infraestrutura de Cidade Inteligente, demonstrando a comunicação entre dispositivos IoT (sensores e atuadores), um Gateway central e um cliente de controle. A arquitetura utiliza diferentes protocolos de comunicação para tarefas específicas, como RESTful API para interação com o usuário, gRPC para controle de dispositivos e Multicast para descoberta de serviços.

## Diagrama da Arquitetura

O sistema é composto por três componentes principais que interagem da seguinte forma:

```
+----------------+      +-----------------------+      +------------------------+
|                |      |                       |      |                        |
|  Cliente       |----->|  Gateway (API REST)   |<---->|  Dispositivos (gRPC)   |
|  (cliente.py)  |      |      (gateway.py)     |      |  (dispositivos.py)     |
|                |      |                       |      |                        |
+----------------+      +-----------+-----------+      +-----------+------------+
                                    |                        ^
                                    | (gRPC)                 | (UDP/Anúncio)
                                    |                        |
                                    v                        |
                             (Comandos)                      |
                                                             | (Multicast/Descoberta)
                          (Dados Sensores/PubSub)            |
                                    ^                        |
                                    |                        |
                                    +------------------------+

```
**Fluxos de Comunicação:**
1.  **Descoberta:** O `Gateway` envia uma mensagem de descoberta via Multicast. Os `Dispositivos` que a recebem respondem com suas informações (ID, tipo, endereço IP, porta gRPC) via UDP.
2.  **Controle (Cliente -> Dispositivo):** O `Cliente` faz uma requisição HTTP (REST) para o `Gateway`. O `Gateway` autentica o cliente, encontra o dispositivo alvo e envia um comando para ele usando gRPC.
3.  **Dados de Sensores (Dispositivo -> Gateway):** Dispositivos do tipo `Continuos` (sensores) publicam suas leituras em um tópico. O `Gateway` se inscreve neste tópico para receber os dados em tempo real.

---

## Principais Componentes

### 1. `gateway.py`
O cérebro da operação. Ele atua como uma ponte entre o mundo externo (cliente) e a rede interna de dispositivos.
- **Servidor RESTful API (Flask):** Expõe endpoints seguros (`/login`, `/consultas`, `/dispositivos`) para o cliente interagir com o sistema. Utiliza **JWT (JSON Web Tokens)** para autenticação.
- **Cliente gRPC:** Inicia chamadas gRPC para os dispositivos a fim de consultar ou alterar seus estados.
- **Servidor de Descoberta (Multicast):** Envia pacotes periodicamente para que novos dispositivos na rede possam se anunciar.
- **Servidor de Anúncios (UDP):** Ouve as respostas dos dispositivos ao processo de descoberta e os adiciona a uma lista de dispositivos ativos.
- **Mecanismo de Heartbeat:** Remove automaticamente dispositivos da lista se eles não se comunicarem dentro de um determinado tempo (`DEVICE_TIMEOUT`), garantindo que a lista esteja sempre atualizada.
- **Broker (Subscriber):** Assina os tópicos de dados de sensores para receber e exibir as leituras.

### 2. `dispositivos.py`
Este arquivo simula os próprios dispositivos IoT. Ele pode ser executado em dois cenários: "Normal" (com todos os dispositivos) ou "Falha" (com um subconjunto).
- **Classes Base:** `Dispositivos` (comum a todos), `Atuador` (pode ter seu estado alterado, ex: `LIGHT_POST`) e `Continuos` (envia dados periodicamente, ex: `TEMPERATURE_SENSOR`).
- **Servidor gRPC:** Cada dispositivo executa seu próprio servidor gRPC para receber comandos do Gateway (`StateDevice`, `ChangeState`, `ChangeTime`).
- **Listener de Descoberta (Multicast):** Ouve as mensagens de descoberta do Gateway e responde com suas informações.
- **Publicador de Dados (Publisher):** Sensores publicam suas leituras em um tópico do broker para que o Gateway (e qualquer outro serviço interessado) possa consumi-las.

### 3. `cliente.py`
Uma interface de linha de comando (CLI) que permite a um usuário controlar e monitorar a cidade inteligente.
- **Cliente REST:** Interage **exclusivamente** com a API REST do Gateway. Ele não tem conhecimento sobre gRPC ou sobre a topologia da rede de dispositivos.
- **Autenticação:** Primeiro, faz login no Gateway para obter um token JWT, que é então usado em todas as requisições subsequentes.
- **Funcionalidades:** Permite ao usuário listar dispositivos online, ligar/desligar atuadores, consultar o estado de um dispositivo e alterar a frequência de envio de dados dos sensores.

---

## Tecnologias Utilizadas
- **Linguagem:** Python 3
- **Comunicação Cliente-Gateway:** API REST (Flask, Flask-RESTful) com autenticação JWT (PyJWT).
- **Comunicação Gateway-Dispositivo:** gRPC e Protocol Buffers (`protobuf`).
- **Descoberta de Serviço:** Multicast e UDP.
- **Streaming de Dados:** Padrão Publish/Subscribe (implementado em `pubsub.py`).
- **Concorrência:** `threading` para executar múltiplos serviços (API, gRPC, listeners) simultaneamente.

---

## Pré-requisitos
Antes de executar, certifique-se de ter o Python 3 instalado e instale as seguintes bibliotecas:

```bash
pip install grpcio
pip install grpcio-tools
pip install protobuf
pip install Flask
pip install Flask-RESTful
pip install PyJWT
pip install requests
```
Ou, se preferir, crie um arquivo `requirements.txt` com o conteúdo acima e execute `pip install -r requirements.txt`.

**Compilação dos Protocol Buffers:**
Os arquivos `.proto` precisam ser compilados para gerar o código Python necessário para gRPC. Execute o seguinte comando a partir da raiz do projeto:
```bash
python -m grpc_tools.protoc -I./protos --python_out=./protos --grpc_python_out=./protos ./protos/messages.proto
```
Isso irá gerar (ou atualizar) os arquivos `messages_pb2.py` e `messages_pb2_grpc.py` no diretório `protos`.

---

## Como Executar a Simulação

Para executar o sistema, você precisará de três terminais separados, executados **nesta ordem**:

**1. Terminal 1: Iniciar o Gateway**
O Gateway deve ser o primeiro a ser executado, pois ele precisa estar pronto para descobrir os dispositivos.
```bash
python gateway.py
```
Você verá logs indicando que os servidores Flask, UDP e de descoberta foram iniciados.

**2. Terminal 2: Iniciar os Dispositivos**
Com o Gateway no ar, inicie os dispositivos. O script pedirá para você escolher um cenário.
```bash
python dispositivos.py
```
Escolha a opção `1` para o cenário normal. Você verá logs de cada dispositivo iniciando seu servidor gRPC e, em seguida, sendo descoberto pelo Gateway (o log de descoberta aparecerá no terminal do Gateway).

**3. Terminal 3: Iniciar o Cliente**
Agora você pode controlar o sistema usando o cliente.
```bash
python cliente.py
```
O cliente fará o login automaticamente e apresentará um menu de opções para interagir com a cidade.

---

## Funcionalidades do Cliente

Após o login bem-sucedido, o cliente pode executar as seguintes ações:

- **Listar todos os dispositivos online:** Mostra o ID e o tipo de cada dispositivo que está atualmente conectado ao Gateway.
- **Ligar/Desligar um dispositivo:** Permite enviar um comando para atuadores (Poste, Semáforo, Câmera) para alterar seu estado.
- **Consultar Estado dos Dispositivos:** Verifica se um atuador específico está ligado ou desligado.
- **Mudar configuração de envio de tempo:** Altera o intervalo (em segundos) com que um sensor (Temperatura, Qualidade do Ar, GPS) envia suas leituras.

### Credenciais Padrão
- **Usuário:** `admin`
- **Senha:** `123`

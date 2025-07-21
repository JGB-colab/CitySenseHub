// Definindo os endpoints

## API REST: 
- Endpoints
   - login
      - 
   -/estados:
    - GET
      -  /estados/id
    - POST
    - PUT
    - PATCH  

  - /dispositivos:
    - GET (consultar)
      - /dispositivos/id

    - POST(criar um novo dispositivo)
      - /dispositvos

    - PUT(atualizar tudo)
      - /dispositivos/id
         ? params :{
            - config=int
         }

    - PATCH (atualização parcial)
       - /dispositivos/id
         ? params :{
            - configurar=int
            - 
         }


> flask swagger: https://medium.com/@gbmsaraujo/usando-swagger-para-documentar-uma-api-em-flask-c9cde85910f0
> grpc: https://www.velotio.com/engineering-blog/grpc-implementation-using-python
> broker(rabbitmq): https://www.rabbitmq.com/tutorials/tutorial-one-python 


### Cliente ###
 - Consulte os estados dos dispositivos conectados.
    - Rota: /estados/id
 - Envie comandos para dispositivos específicos (
    - Rota: e.g., ligar/desligar
       -  lâmpadas dos postes, mudar a configuração da câmera, mudar a configuração do semáforo). 
      - São exemplos de mudança de 
        - configuração: alterar a resolução da imagem de uma camera de HD para FullHD ou mesmo 4k
        - alterar o tempo de permanência do semafório como fechado (Sinal Vermelho) de 10 para 15 segundos.
        - outros exemplos de configurações ficam a carga da equipe.
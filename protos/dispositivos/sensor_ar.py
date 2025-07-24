from dispositivos import Continuos
import threading
import time

if __name__ == "__main__":
    print("Iniciando dispositivo Sensor de Ar autônomo...")
    gps = Continuos(tipo="AIR_QUALITY_SENSOR", data_unit="") 
    
    gps_thread = threading.Thread(target=gps.iniciar, daemon=True)
    gps_thread.start()

    try:
        while True:
            # O loop principal pode ficar ocioso ou fazer outras tarefas se necessário.
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nDesligando o dispositivo GPS...")
        gps.parar() # Sinaliza para o dispositivo encerrar suas threads internas.
        time.sleep(1) # Dá um tempinho para as threads fecharem.
        print("Dispositivo GPS encerrado.")
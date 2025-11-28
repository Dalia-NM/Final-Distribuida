import time
import json
import pika
import sys
from deck import Baraja

try:
    import pika
    _HAS_PIKA = True
except Exception:
    _HAS_PIKA = False

SIMULACIONES = 10000

def run_productor(publish=True):
    print("Iniciando la configuración de la simulación...")
    
    # 1. Configurar la Baraja
    baraja = Baraja()
    
    # --- EJEMPLOS DE MODIFICACIÓN (Opcional) ---
    # baraja.modificar_cantidad('A', 8)
    # baraja.modificar_cantidad('10', 0)
    # -----------------------------------------

    baraja_json = baraja.to_json()
    
    canal = None
    conexion = None
    if publish:
        if not _HAS_PIKA:
            print("pika no disponible — publicación deshabilitada")
            publish = False
        else:
            try:
                conexion = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
                canal = conexion.channel()
            except Exception as e:
                print(f"No fue posible conectar con RabbitMQ: {e}. Publicación deshabilitada.")
                publish = False

    # Declarar colas (Asegura que existen)
    if publish and canal is not None:
        canal.queue_declare(queue='baraja', durable=True) 
        canal.queue_declare(queue='escenarios', durable=True)
    
    #Publicar la Configuración de la Baraja (Modelo)
    print(f"Publicando la configuración de la baraja. Total de cartas: {baraja.obtener_total()}")
    if publish:
        canal.basic_publish(
        exchange='',
        routing_key='baraja',
        body=baraja_json,
        properties=pika.BasicProperties(
            delivery_mode=pika.DeliveryMode.Transient,
            expiration='30000' # Expira en 30 segundos (time-out delivery)
        )
        )

    #Publicar Escenarios
    print(f"Generando y publicando {SIMULACIONES} escenarios...")
    for i in range(1, SIMULACIONES + 1):
        message = json.dumps({'sim_id': i})
        if publish:
            canal.basic_publish(
            exchange='',
            routing_key='escenarios',
            body=message,
            properties=pika.BasicProperties(
                delivery_mode=pika.DeliveryMode.Transient
            )
            )
    
    if publish and conexion is not None:
        print(f"{SIMULACIONES} escenarios publicados.")
        conexion.close()
    else:
        print("error en modo.")

if __name__ == '__main__':
    run_productor(publish=True)

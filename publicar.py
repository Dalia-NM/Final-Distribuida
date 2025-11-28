import pika
import json
import sys

# Configuración de la baraja
# La suma total de los valores no debe exceder 52 para ser una baraja estándar.
config = {
  "A": 4, "2": 4, "3": 4, "4": 4, "5": 4,
  "6": 4, "7": 4, "8": 4, "9": 4, "10": 4,
  "J": 4, "Q": 4, "K": 4
}


TOTAL_CARTAS = sum(config.values())
TTL_EXPIRATION_MS = '30000' # 30 segundos de caducidad (Time-out Delivery)

if TOTAL_CARTAS > 52:
    print(f"ADVERTENCIA: La configuracion excede las 52 cartas ({TOTAL_CARTAS}).")
elif TOTAL_CARTAS == 0:
    print("La baraja tiene 0 cartas y es Iiposible simular.")
    sys.exit(1)

try:
    # Conexión con RabbitMQ
    conn = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    ch = conn.channel()
    
    # Declarar la cola
    ch.queue_declare(queue='baraja', durable=True)
    
    # Publicar el mensaje
    ch.basic_publish(
        exchange='', 
        routing_key='baraja', 
        body=json.dumps(config),
        properties=pika.BasicProperties(
            delivery_mode=pika.DeliveryMode.Transient,
            expiration=TTL_EXPIRATION_MS         
        )
    )
    
    print(f"Publicado configuración de baraja (Total: {TOTAL_CARTAS})")
    conn.close()

except pika.exceptions.AMQPConnectionError as e:
    print(f"\nNo se pudo conectar a RabbitMQ.")
    print(f"Detalle: {e}")
except Exception as e:
    print(f"\nERROR desconocido durante la publicación: {e}")


import json
import time
import os
import sys
import pika
# Soportar ausencia de pika
try:
    import pika
    _HAS_PIKA = True
except Exception:
    _HAS_PIKA = False

# Importar la lógica centralizada del modelo
from deck import Baraja, simulate_blackjack

# --- Lógica del Consumidor ---

def callback_escenario(ch, method, properties, body, baraja_config):
    """Callback que procesa un escenario y publica el resultado."""
    try:
        if isinstance(body, bytes):
            body = body.decode('utf-8')
        scenario_data = json.loads(body)
        sim_id = scenario_data['sim_id']
        
        # Ejecutar el modelo importado
        result = simulate_blackjack(baraja_config)
        
        # Publicar resultado
        result_message = json.dumps({'sim_id': sim_id, 'result': result})
        ch.basic_publish(
            exchange='',
            routing_key='resultados',
            body=result_message,
            properties=pika.BasicProperties(
                delivery_mode=pika.DeliveryMode.Transient
            )
        )
        
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        print(f"CONSUMER {os.getpid()} Error processing scenario: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag) 

def run_consumer():
    import os 
    
    if not _HAS_PIKA:
        print("error en libreria")
        baraja_default = Baraja()
        baraja_config = baraja_default.config
        demo_count = 20
        print(f"Consumidor {os.getpid()}: Ejecutando {demo_count} simulaciones locales...")
        for i in range(1, demo_count + 1):
            res = simulate_blackjack(baraja_config)
            print(f"LOCAL SIM {i}: {res}")
        return

    print(f"Consumidor {os.getpid()}: Iniciando...")
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()

    # 1. Declarar colas
    channel.queue_declare(queue='baraja', durable=True)
    channel.queue_declare(queue='escenarios', durable=True)
    channel.queue_declare(queue='resultados', durable=False)

    # 2. Obtener la Configuración de la Baraja (Modelo)
    print(f"Consumidor {os.getpid()}: Esperando la configuración de la baraja...")
    
    method_frame, header_frame, body = channel.basic_get('baraja', auto_ack=True)

    while body is None:
        time.sleep(1)
        method_frame, header_frame, body = channel.basic_get('baraja', auto_ack=True)

    if isinstance(body, bytes):
        body = body.decode('utf-8')

    baraja_config = json.loads(body)
    print(f"Consumidor{os.getpid()}: Baraja cargada. Total de cartas: {sum(baraja_config.values())}")
    
    # 3. Consumir escenarios y ejecutar el callback
    channel.basic_qos(prefetch_count=1) 
    
    channel.basic_consume(
        queue='escenarios',
        on_message_callback=lambda ch, method, properties, body: callback_escenario(ch, method, properties, body, baraja_config)
    )

    print(f"CONSUMER {os.getpid()}: Esperando escenarios...")
    channel.start_consuming()

if __name__ == '__main__':
    run_consumer() = False
    if len(sys.argv) > 1 and sys.argv[1] in ('local', 'l'):
        force_local = True


    run_consumer()

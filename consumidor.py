import json
import random
import time
import os

# Soportar ausencia de pika (modo demo/local)
try:
    import pika
    _HAS_PIKA = True
except Exception:
    _HAS_PIKA = False

# Usar la implementación actual en deck.py
from deck import Baraja, calcular_mano

# --- Lógica Principal del Modelo de Blackjack ---

def simulate_blackjack(baraja_config):
    """
    Ejecuta una simulación simplificada de una mano de Blackjack.
    Retorna 'VICTORIA', 'DERROTA', o 'EMPATE'.
    """
    # 1. Crear una baraja para la simulación (Lista de cartas)
    deck = []
    for card_value, count in baraja_config.items():
        deck.extend([card_value] * count)
        
    random.shuffle(deck)

    # 2. Repartir manos
    try:
        player_hand = [deck.pop(), deck.pop()]
        dealer_hand = [deck.pop(), deck.pop()] # Segunda carta oculta no relevante para la simulación simple
    except IndexError:
        # Esto no debería pasar si la baraja está bien configurada
        return "ERROR_NO_CARTAS" 
    
    # 3. Turno del Jugador (Pide hasta 17 o se pasa)
    while calcular_mano(player_hand) < 17:
        try:
            player_hand.append(deck.pop())
        except IndexError:
            break
            
    player_score = calcular_mano(player_hand)
    
    if player_score > 21:
        return "DERROTA" # Jugador se pasa (Bust)

    # 4. Turno del Crupier (Pide hasta 17 o se pasa)
    dealer_score = calcular_mano(dealer_hand)
    while dealer_score < 17:
        try:
            dealer_hand.append(deck.pop())
            dealer_score = calcular_mano(dealer_hand)
        except IndexError:
            break

    if dealer_score > 21:
        return "VICTORIA" # Crupier se pasa (Bust)

    # 5. Comparar resultados
    if player_score > dealer_score:
        return "VICTORIA"
    elif player_score < dealer_score:
        return "DERROTA"
    else:
        return "EMPATE"

# --- Lógica del Consumidor ---

def callback_escenario(ch, method, properties, body, baraja_config):
    """Callback que procesa un escenario y publica el resultado."""
    try:
        # body puede venir en bytes desde pika; aseguramos str antes de parsear
        if isinstance(body, bytes):
            body = body.decode('utf-8')
        scenario_data = json.loads(body)
        sim_id = scenario_data['sim_id']
        
        # Ejecutar el modelo
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
        print(f"CONSUMER {os.getpid()}: Sim ID {sim_id} -> {result}")

    except Exception as e:
        print(f"CONSUMER {os.getpid()} Error processing scenario: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag) # Reencolar en caso de error

def run_consumer(force_local=False):
    import os # Necesario para obtener el PID
    print(f"CONSUMER {os.getpid()}: Iniciando...")
    
    # Si pika no está disponible o se forzó modo local, ejecutamos en modo local (demo)
    if (not _HAS_PIKA) or force_local:
        print("pika no disponible — ejecutando consumidor en modo local (demo)")
        # Construir configuración por defecto usando Baraja
        baraja_default = Baraja()
        baraja_config = baraja_default.config

        # Simular consumo de escenarios locales (ejemplo reducido)
        demo_count = 20
        print(f"CONSUMER {os.getpid()}: Ejecutando {demo_count} simulaciones locales...")
        for i in range(1, demo_count + 1):
            res = simulate_blackjack(baraja_config)
            print(f"LOCAL SIM {i}: {res}")
        return

    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()

    # 1. Declarar colas
    channel.queue_declare(queue='baraja', durable=True)
    channel.queue_declare(queue='escenarios', durable=True)
    channel.queue_declare(queue='resultados', durable=False)

    # 2. Obtener la Configuración de la Baraja (Modelo) - ¡Solo una vez!
    print(f"CONSUMER {os.getpid()}: Esperando la configuración de la baraja...")
    
    # Esperar y consumir UN SOLO mensaje de la cola 'baraja'
    method_frame, header_frame, body = channel.basic_get('baraja', auto_ack=True)

    while body is None:
        time.sleep(1)
        method_frame, header_frame, body = channel.basic_get('baraja', auto_ack=True)

    if isinstance(body, bytes):
        body = body.decode('utf-8')

    baraja_config = json.loads(body)
    print(f"CONSUMER {os.getpid()}: Baraja cargada. Total de cartas: {sum(baraja_config.values())}")
    
    # 3. Consumir escenarios y ejecutar el callback
    channel.basic_qos(prefetch_count=1) # Solo un mensaje a la vez por consumidor
    
    # Pasar la configuración de la baraja al callback
    channel.basic_consume(
        queue='escenarios',
        on_message_callback=lambda ch, method, properties, body: callback_escenario(ch, method, properties, body, baraja_config)
    )

    print(f"CONSUMER {os.getpid()}: Esperando escenarios...")
    channel.start_consuming()

if __name__ == '__main__':
    import sys
    force_local = False
    if len(sys.argv) > 1 and sys.argv[1] in ('local', 'l'):
        force_local = True

    run_consumer()
import time
import json
import pika

# Intentamos importar pika, pero no abortaremos si no está disponible (permitir pruebas locales).
try:
    import pika
    _HAS_PIKA = True
except Exception:
    _HAS_PIKA = False

from deck import Baraja, calcular_mano

SIMULACIONES = 10000

def run_productor(publish=True):
    print("Iniciando la configuración de la simulación...")
    
    # 1. Configurar la Baraja
    # Usar la clase `Baraja` que está en deck.py
    baraja = Baraja()
    
    # --- EJEMPLOS DE MODIFICACIÓN (Opcional) ---
    # 1) Cambiar solo unos valores (int) — respetará MAX a menos que desactives limit
    # baraja.modificar_cantidad('A', 8)
    # baraja.modificar_cantidad('10', 0)

    # 2) Cambiar varias cantidades a la vez (modificar_varias)
    # baraja.modificar_varias({'A':8, 'K':7})

    # 3) Si quieres permitir configuraciones libres que excedan 52 cartas,
    #    desactiva el límite llamando `baraja.set_max(None)` antes de aplicar cambios.
    #    Ejemplo: crear 7 reyes y 7 ases y dejar el resto igual
    # baraja.set_max(None)
    # baraja.modificar_varias({'A': 7, 'K': 7})

    # 4) Para tener 52 ases (ejemplo extremo), desactiva el límite y aplica
    # baraja.set_max(None)
    # baraja.modificar_cantidad('A', 52)
    # -----------------------------------------

    baraja_json = baraja.to_json()
    
    # 2. Conexión con RabbitMQ
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

    # Declarar colas (Asegura que existen) — solo si existe canal
    if publish and canal is not None:
        canal.queue_declare(queue='baraja', durable=True)
        canal.queue_declare(queue='escenarios', durable=True)
    else:
        # En modo local o si la conexión falló no intentamos llamar métodos sobre None
        if publish:
            print("Advertencia: publish=True pero canal es None. No se declararon colas.")
        else:
            print("Modo local o publicación deshabilitada — no se declararon colas en broker.")
    
    # 3. Publicar la Configuración de la Baraja (Modelo)
    # TTL de 30 segundos, solo para demostrar la politica de caducidad.
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

    # 4. Publicar Escenarios
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
        print(f"{SIMULACIONES} escenarios publicados exitosamente.")
        conexion.close()
    else:
        print("Modo local -> no se publicó en RabbitMQ.")

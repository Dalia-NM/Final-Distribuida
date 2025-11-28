import json
import time
import sys
import os

import pika
import tqdm


# Importar la clase Baraja para mostrar la tabla de configuración
from deck import Baraja 

NUM_SIMULATIONS = 10000

# Códigos de color ANSI
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
ENDC = '\033[0m'

class Dashboard:
    """Dashboard de Consola para visualizar el progreso y resultados de Monte Carlo."""

    def __init__(self, total: int = NUM_SIMULATIONS):
        self.victories = 0
        self.defeats = 0
        self.ties = 0
        self.total_processed = 0
        self.baraja_config = None
        self.total = total
        
        self.bar = tqdm(total=total, desc=f"{BLUE}Progreso de Simulación{ENDC}", unit="sim", file=sys.stdout)
        self.bar = None

    def print_config_table(self):
        """Muestra la configuración de la baraja como tabla en la consola."""
        if not self.baraja_config:
            print(f"{RED}Error: Configuración de baraja no cargada.{ENDC}")
            return

        # Normalizar a objeto Baraja
        try:
            if isinstance(self.baraja_config, str):
                baraja_obj = Baraja.from_json(self.baraja_config)
            else: # Si ya es un dict
                baraja_obj = Baraja()
                baraja_obj.config = self.baraja_config
        except Exception:
            baraja_obj = Baraja()

        print("\n" + "="*60)
        print(f"{BLUE}CONFIGURACIÓN DE BARAJA ({baraja_obj.obtener_total()} cartas totales){ENDC}")
        print("-" * 60)
        header = "| " + " | ".join([f"{v:^4}" for v in baraja_obj.CARTAS_VALORES]) + " |"
        print(header)
        print("-" * 60)
        quantities = "| " + " | ".join([f"{baraja_obj.config.get(v,0):^4}" for v in baraja_obj.CARTAS_VALORES]) + " |"
        print(quantities)
        print("="*60 + "\n")

    def update_stats(self, result_data):
        """Actualiza los contadores y el log en tiempo real."""
        result = result_data['result']
        self.total_processed += 1

        color = ENDC
        if result == 'VICTORIA':
            self.victories += 1
            color = GREEN
        elif result == 'DERROTA':
            self.defeats += 1
            color = RED
        elif result == 'EMPATE':
            self.ties += 1
            color = YELLOW

        # Actualizar la barra de progreso
        if self.bar is not None:
            self.bar.update(1)
        
        # Log de resultados en tiempo real
        sys.stdout.write(
            f"\r{color}[LOG]{ENDC} Sim ID {result_data['sim_id']}: {color}{result}{ENDC} | "
            f"V: {GREEN}{self.victories}{ENDC} | "
            f"D: {RED}{self.defeats}{ENDC} | "
            f"E: {YELLOW}{self.ties}{ENDC} | "
            f"Total: {self.total_processed}"
        )
        sys.stdout.flush()

    def final_report(self):
        """Muestra el reporte final, incluyendo probabilidades y gráfico."""
        if self.bar is not None:
            self.bar.close()

        if self.total_processed == 0:
            print(f"\n{RED}No se recibieron resultados.{ENDC}")
            return

        win_prob = (self.victories / self.total_processed) * 100
        lose_prob = (self.defeats / self.total_processed) * 100
        tie_prob = (self.ties / self.total_processed) * 100

        print("\n\n" + "="*60)
        print(f"{BLUE}--- REPORTE FINAL DE LA SIMULACIÓN MONTE CARLO ---{ENDC}")
        print("-" * 60)
        print(f"Simulaciones Totales: {self.total_processed}")
        print("-" * 60)
        print(f"Victorias: {GREEN}{self.victories}{ENDC} ({win_prob:.2f}%)")
        print(f"Derrotas:  {RED}{self.defeats}{ENDC} ({lose_prob:.2f}%)")
        print(f"Empates:   {YELLOW}{self.ties}{ENDC} ({tie_prob:.2f}%)")
        print("-" * 60)
        print(f"{GREEN}PROBABILIDAD DE GANAR: {win_prob:.2f}%{ENDC}")
        print("="*60)
        self.print_chart(win_prob, lose_prob, tie_prob)

    def print_chart(self, win, lose, tie):
        """Muestra un gráfico de barras simple en texto ASCII."""
        print(f"\n{BLUE}Distribución de Resultados:{ENDC}")
        scale = 50 / 100
        win_bar = '#' * int(win * scale)
        lose_bar = '#' * int(lose * scale)
        tie_bar = '#' * int(tie * scale)
        
        print(f"Victoria: {GREEN}{win_bar}{ENDC} {win:.2f}%")
        print(f"Derrota:  {RED}{lose_bar}{ENDC} {lose:.2f}%")
        print(f"Empate:   {YELLOW}{tie_bar}{ENDC} {tie:.2f}%")


def run_dashboard():
    dashboard = Dashboard(total=NUM_SIMULATIONS)
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    except Exception as e:
        print(f"ERROR: no fue posible conectar a RabbitMQ en 'localhost': {e}")
        return

    channel = connection.channel()
    channel.queue_declare(queue='baraja', durable=True)
    channel.queue_declare(queue='resultados', durable=False)

    print("DASHBOARD: Esperando la configuración de la baraja...")
    
    # 1. Obtener la Configuración Inicial
    method_frame, header_frame, body = channel.basic_get('baraja', auto_ack=True)
    while body is None:
        time.sleep(1)
        method_frame, header_frame, body = channel.basic_get('baraja', auto_ack=True)

    if isinstance(body, bytes):
        baraja_payload = body.decode('utf-8')
    else:
        baraja_payload = body

    dashboard.baraja_config = baraja_payload
    dashboard.print_config_table()
    print(f"DASHBOARD: Se realizarán {NUM_SIMULATIONS} pruebas.\n")
    
    # 2. Consumir Resultados
    def callback(ch, method, properties, body):
        if isinstance(body, bytes):
            body = body.decode('utf-8')
        result_data = json.loads(body)
        dashboard.update_stats(result_data)
        ch.basic_ack(delivery_tag=method.delivery_tag)

        if dashboard.total_processed >= NUM_SIMULATIONS:
            ch.stop_consuming()

    channel.basic_consume(queue='resultados', on_message_callback=callback, auto_ack=False)

    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print("\nDASHBOARD: Interrumpido por el usuario.")
    finally:
        dashboard.final_report()
        connection.close()

if __name__ == '__main__':
    run_dashboard()

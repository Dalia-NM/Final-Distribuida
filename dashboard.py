import json
import random
import time
import os
import sys

try:
    import pika
    _HAS_PIKA = True
except Exception:
    _HAS_PIKA = False

# Usar la implementación actual en deck.py
from deck import Baraja, calcular_mano

# Proceso/escenarios a esperar (coincide con pro.py)
NUM_SIMULATIONS = 10000

# Intentamos importar tqdm para barra de progreso
try:
    from tqdm import tqdm
    _HAS_TQDM = True
except Exception:
    tqdm = None
    _HAS_TQDM = False

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

def run_consumer():
    import os # Necesario para obtener el PID
    print(f"CONSUMER {os.getpid()}: Iniciando...")
    
    # Si pika no está disponible, ejecutamos una versión local/demo
    if not _HAS_PIKA:
        print(f"DASHBOARD {os.getpid()}: pika no disponible — ejecutando demo local")
        baraja_default = Baraja()
        baraja_config = baraja_default.config
        # Mostrar algunas simulaciones de dashboard
        for i in range(1, 11):
            print(f"DASH DEMO {i}: {simulate_blackjack(baraja_config)}")
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


# ------------------ GUI using Tkinter + Matplotlib ------------------
try:
    import tkinter as tk
    from tkinter import ttk
    from tkinter import scrolledtext
    import matplotlib
    matplotlib.use('TkAgg')
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    _HAS_GUI = True
except Exception:
    tk = None
    ttk = None
    Figure = None
    FigureCanvasTkAgg = None
    _HAS_GUI = False

import threading
import queue as _queue


class GuiDashboard:
    """Interfaz gráfica que muestra la configuración y un gráfico en ventana."""
    def __init__(self, total=NUM_SIMULATIONS):
        if not _HAS_GUI:
            raise RuntimeError('No hay soporte GUI (tkinter/matplotlib)')

        self.total = total
        self.root = tk.Tk()
        self.root.title('Dashboard - Simulaciones Blackjack')

        # Estadísticas
        self.victories = 0
        self.defeats = 0
        self.ties = 0
        self.total_processed = 0

        # Mensaje de config (json str or dict)
        self.baraja_config = None

        # Cola de mensajes del consumidor
        self.msg_q = _queue.Queue()

        # Layout: en la izquierda la tabla de configuración, a la derecha el gráfico
        main = ttk.Frame(self.root, padding=8)
        main.pack(fill='both', expand=True)

        left = ttk.Frame(main)
        left.pack(side='left', fill='y', padx=8)

        right = ttk.Frame(main)
        right.pack(side='right', fill='both', expand=True, padx=8)

        # Tabla de configuración (Treeview)
        ttk.Label(left, text='Configuración de Baraja', font=('TkDefaultFont', 12, 'bold')).pack(anchor='w')
        self.table = ttk.Treeview(left, columns=('valor', 'cantidad'), show='headings', height=14)
        self.table.heading('valor', text='Valor')
        self.table.heading('cantidad', text='Cantidad')
        self.table.column('valor', width=50, anchor='center')
        self.table.column('cantidad', width=80, anchor='center')
        self.table.pack(fill='y')

        # Stats text
        stats_frame = ttk.Frame(left, padding=(0,12,0,0))
        stats_frame.pack(fill='x')
        self.stats_label = ttk.Label(stats_frame, text='V: 0  D: 0  E: 0  Total: 0')
        self.stats_label.pack()
        # Final probabilities shown under counters
        self.prob_label = ttk.Label(stats_frame, text='Probabilidades: V: 0.00%  D: 0.00%  E: 0.00%')
        self.prob_label.pack()

        # Botones
        btn_frame = ttk.Frame(left, padding=(0,8,0,0))
        btn_frame.pack(fill='x')
        ttk.Button(btn_frame, text='Salir', command=self._on_close).pack(fill='x')

        # Matplotlib figure
        self.fig = Figure(figsize=(5,3))
        self.ax = self.fig.add_subplot(111)
        self.bars = self.ax.bar(['VICTORIA','DERROTA','EMPATE'], [0,0,0], color=['green','red','gold'])
        self.ax.set_ylim(0, 100)
        self.ax.set_ylabel('Porcentaje (%)')
        self.ax.set_title('Distribución de resultados')
        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        self.canvas.get_tk_widget().pack(fill='both', expand=True)

        # Log area (scrollable)
        log_frame = ttk.Frame(left)
        log_frame.pack(fill='both', expand=False, pady=(8,0))
        ttk.Label(log_frame, text='Log (últimos resultados)').pack(anchor='w')
        self.log_widget = scrolledtext.ScrolledText(log_frame, height=10, wrap='none')
        self.log_widget.pack(fill='both', expand=True)
        self.log_widget.configure(state='disabled')

        # Programar el polling de la cola
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)
        self._running = False

    def _on_close(self):
        self._running = False
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass

    def set_config(self, baraja_json_or_dict):
        # Almacena config y muestra en la tabla
        self.baraja_config = baraja_json_or_dict
        if isinstance(baraja_json_or_dict, str):
            try:
                d = json.loads(baraja_json_or_dict)
            except Exception:
                d = {}
        else:
            d = baraja_json_or_dict

        # Limpiar y poblar
        for i in self.table.get_children():
            self.table.delete(i)
        for v in Baraja.CARTAS_VALORES:
            self.table.insert('', 'end', values=(v, d.get(v,0)))

    def start(self):
        """Inicia la GUI mainloop (bloqueante). Debe haberse iniciado el consumidor en otro hilo que ponga mensajes en msg_q."""
        self._running = True
        self._consume_queue()
        self.root.mainloop()

    def _consume_queue(self):
        # Leer hasta 50 mensajes de la cola y procesarlos, luego reprogramar after
        processed = 0
        while processed < 50:
            try:
                data = self.msg_q.get_nowait()
            except _queue.Empty:
                break
            self._apply_result(data)
            processed += 1

        if self._running:
            self.root.after(100, self._consume_queue)

    def _apply_result(self, result_data):
        res = result_data.get('result')
        self.total_processed += 1
        if res == 'VICTORIA':
            self.victories += 1
        elif res == 'DERROTA':
            self.defeats += 1
        elif res == 'EMPATE':
            self.ties += 1

        self._update_stats_widgets()
        # append to GUI log
        try:
            self.log_widget.configure(state='normal')
            self.log_widget.insert('end', f"Sim {result_data.get('sim_id')}: {res}\n")
            self.log_widget.see('end')
            self.log_widget.configure(state='disabled')
        except Exception:
            pass

    def _update_stats_widgets(self):
        # Update label
        self.stats_label.config(text=f'V: {self.victories}  D: {self.defeats}  E: {self.ties}  Total: {self.total_processed}')

        # Update bars (percentages)
        total = max(1, self.total_processed)
        win = (self.victories/total)*100
        lose = (self.defeats/total)*100
        tie = (self.ties/total)*100

        vals = [win, lose, tie]
        for bar, h in zip(self.bars, vals):
            bar.set_height(h)
        self.ax.set_ylim(0, max(100, max(vals)*1.1))
        self.canvas.draw_idle()
        # update probability label
        win = (self.victories/total)*100
        lose = (self.defeats/total)*100
        tie = (self.ties/total)*100
        self.prob_label.config(text=f'Probabilidades: V: {win:.2f}%  D: {lose:.2f}%  E: {tie:.2f}%')

    def final_report(self):
        # Mostrar ventana resumen al cerrar
        if self.bar is not None:
            self.bar.close()

        if self.total_processed == 0:
            try:
                import tkinter.messagebox as mb
                mb.showinfo('Dashboard', 'No se recibieron resultados')
            except Exception:
                pass
            return

        win_prob = (self.victories / self.total_processed) * 100
        lose_prob = (self.defeats / self.total_processed) * 100
        tie_prob = (self.ties / self.total_processed) * 100

        msg = f"Sim total: {self.total_processed}\nVictorias: {self.victories} ({win_prob:.2f}%)\nDerrotas: {self.defeats} ({lose_prob:.2f}%)\nEmpates: {self.ties} ({tie_prob:.2f}%)"
        try:
            import tkinter.messagebox as mb
            mb.showinfo('Reporte final', msg)
        except Exception:
            print(msg)


def _start_consumer_thread_for_gui(amqp_host, queue_name, dashboard_widget):
    """Inicia un hilo que crea una conexión nueva y consume la cola 'queue_name', poniendo mensajes en dashboard_widget.msg_q"""
    def _consumer():
        try:
            conn = pika.BlockingConnection(pika.ConnectionParameters(amqp_host))
            ch = conn.channel()
        except Exception as e:
            print(f"GUI consumer: error al conectar a RabbitMQ: {e}")
            return

        while dashboard_widget._running and dashboard_widget.total_processed < dashboard_widget.total:
            try:
                method_frame, header_frame, body = ch.basic_get(queue_name, auto_ack=False)
                if body is None:
                    time.sleep(0.1)
                    continue

                if isinstance(body, bytes):
                    body = body.decode('utf-8')
                data = json.loads(body)
                dashboard_widget.msg_q.put(data)
                if method_frame is not None:
                    ch.basic_ack(delivery_tag=method_frame.delivery_tag)
            except Exception:
                time.sleep(0.5)
                continue

        try:
            conn.close()
        except Exception:
            pass

    t = threading.Thread(target=_consumer, daemon=True)
    t.start()
    return t


def _consume_generator(channel, queue_name):
    """Generator simple que hace basic_get en bucle (no bloqueante) y yield los mensajes.

    Usado para hilo consumidor sencillo que hace polling. Evita bloqueo de start_consuming en hilo.
    """
    while True:
        try:
            method_frame, header_frame, body = channel.basic_get(queue_name, auto_ack=False)
            if body is not None:
                yield (method_frame, header_frame, body)
            else:
                time.sleep(0.1)
        except Exception:
            time.sleep(0.5)
            continue


# --------------------- DASHBOARD (UI ASCII + tabla) ---------------------
class Dashboard:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    ENDC = '\033[0m'
    BLUE = '\033[94m'

    def __init__(self, total: int = NUM_SIMULATIONS):
        self.victories = 0
        self.defeats = 0
        self.ties = 0
        self.total_processed = 0
        self.baraja_config = None
        self.total = total
        self.log_entries = []  # Initialize log_entries to store results
        if _HAS_TQDM:
            self.bar = tqdm(total=total, desc=f"{self.BLUE}Progreso de Simulación{self.ENDC}", unit="sim")
        else:
            self.bar = None

    def print_config_table(self):
        if not self.baraja_config:
            print(f"{self.RED}Error: Configuración de baraja no cargada.{self.ENDC}")
            return

        # normalizar a objeto Baraja
        try:
            if isinstance(self.baraja_config, str):
                baraja_obj = Baraja.from_json(self.baraja_config)
            else:
                baraja_obj = Baraja()
                baraja_obj.config = self.baraja_config
        except Exception:
            baraja_obj = Baraja()

        print("\n" + "="*60)
        print(f"{self.BLUE}CONFIGURACIÓN DE BARAJA ({baraja_obj.obtener_total()} cartas totales){self.ENDC}")
        print("-" * 60)
        header = "| " + " | ".join([f"{v:^4}" for v in baraja_obj.CARTAS_VALORES]) + " |"
        print(header)
        print("-" * 60)
        quantities = "| " + " | ".join([f"{baraja_obj.config.get(v,0):^4}" for v in baraja_obj.CARTAS_VALORES]) + " |"
        print(quantities)
        print("="*60 + "\n")

    def update_stats(self, result_data):
        result = result_data['result']
        self.total_processed += 1

        color = self.ENDC
        if result == 'VICTORIA':
            self.victories += 1
            color = self.GREEN
        elif result == 'DERROTA':
            self.defeats += 1
            color = self.RED
        elif result == 'EMPATE':
            self.ties += 1
            color = self.YELLOW

        if self.bar is not None:
            self.bar.update(1)
        else:
            print(f"PROGRESO: {self.total_processed}/{self.total}")

        sys.stdout.write(f"\r{color}[LOG]{self.ENDC} Sim ID {result_data['sim_id']}: {color}{result}{self.ENDC} | V: {self.GREEN}{self.victories}{self.ENDC} | D: {self.RED}{self.defeats}{self.ENDC} | E: {self.YELLOW}{self.ties}{self.ENDC} | Total: {self.total_processed}")
        sys.stdout.flush()
        # Store entry for final full log
        self.log_entries.append(f"Sim ID {result_data['sim_id']}: {result}")

    def final_report(self):
        if self.bar is not None:
            self.bar.close()

        if self.total_processed == 0:
            print(f"\n{self.RED}No se recibieron resultados.{self.ENDC}")
            return

        win_prob = (self.victories / self.total_processed) * 100
        lose_prob = (self.defeats / self.total_processed) * 100
        tie_prob = (self.ties / self.total_processed) * 100

        print("\n\n" + "="*60)
        print(f"{self.BLUE}--- REPORTE FINAL DE LA SIMULACIÓN MONTE CARLO ---{self.ENDC}")
        print("-" * 60)
        print(f"Simulaciones Totales: {self.total_processed}")
        print("-" * 60)
        print(f"Victorias: {self.GREEN}{self.victories}{self.ENDC} ({win_prob:.2f}%)")
        print(f"Derrotas:  {self.RED}{self.defeats}{self.ENDC} ({lose_prob:.2f}%)")
        print(f"Empates:   {self.YELLOW}{self.ties}{self.ENDC} ({tie_prob:.2f}%)")
        print("-" * 60)
        print(f"{self.GREEN}PROBABILIDAD DE GANAR: {win_prob:.2f}%{self.ENDC}")
        print("="*60)
        self.print_chart(win_prob, lose_prob, tie_prob)

        # Print full log of results
        print('\n' + '-'*60)
        print('LOG DE SIMULACIONES (todos los resultados):')
        for entry in self.log_entries:
            print(entry)
    def print_chart(self, win, lose, tie):
        print(f"\n{self.BLUE}Distribución de Resultados:{self.ENDC}")
        scale = 50 / 100
        win_bar = '#' * int(win * scale)
        lose_bar = '#' * int(lose * scale)
        tie_bar = '#' * int(tie * scale)
        print(f"Victoria: {self.GREEN}{win_bar}{self.ENDC} {win:.2f}%")
        print(f"Derrota:  {self.RED}{lose_bar}{self.ENDC} {lose:.2f}%")
        print(f"Empate:   {self.YELLOW}{tie_bar}{self.ENDC} {tie:.2f}%")


def run_dashboard(local_demo=False):

    if local_demo:
        print("Modo local/demo está deshabilitado")
        return

    if not _HAS_PIKA:
        print("ERROR: 'pika' no está instalado.")
        print("Instala pika: pip install pika")
        return

    # Selección GUI vs terminal
    use_gui = _HAS_GUI and not any(arg in ('--nogui', 'nogui') for arg in sys.argv)
    if use_gui:
        gui = GuiDashboard(total=NUM_SIMULATIONS)
    else:
        dashboard = Dashboard(total=NUM_SIMULATIONS)
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    except Exception as e:
        print(f"ERROR: no fue posible conectar a RabbitMQ en 'localhost': {e}")
        print("Asegúrate de que RabbitMQ esté corriendo y accesible en localhost y luego reintenta.")
        return

    channel = connection.channel()

    channel.queue_declare(queue='baraja', durable=True)
    channel.queue_declare(queue='resultados', durable=False)

    print("DASHBOARD: Esperando la configuración de la baraja...")
    method_frame, header_frame, body = channel.basic_get('baraja', auto_ack=True)
    while body is None:
        time.sleep(1)
        method_frame, header_frame, body = channel.basic_get('baraja', auto_ack=True)

    if isinstance(body, bytes):
        baraja_payload = body.decode('utf-8')
    else:
        baraja_payload = body

    if use_gui:
        gui.set_config(baraja_payload)
        # start consumer thread that reads 'resultados' and posts to GUI.queue
        gui._running = True
        consumer_thread = _start_consumer_thread_for_gui('localhost', 'resultados', gui)
        # launch the GUI mainloop (blocks)
        gui.start()
        gui.final_report()
        try:
            consumer_thread.join(timeout=0.1)
        except Exception:
            pass
        connection.close()
        return

    dashboard.baraja_config = baraja_payload

    dashboard.print_config_table()
    print(f"DASHBOARD: Se realizarán {NUM_SIMULATIONS} pruebas.\n")

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
        print("DASHBOARD: Interrumpido por el usuario.")
    finally:
        dashboard.final_report()
        connection.close()

if __name__ == '__main__':
    # Por defecto ejecutar dashboard; usa `python dashboard.py consumer` para modo consumidor
    import sys as _sys
    mode = _sys.argv[1] if len(_sys.argv) > 1 else 'dashboard'
    # local demo is disabled for dashboard; ignore any 'local' flags
    if mode in ('consumer', 'c'):
        run_consumer()
    else:
        run_dashboard()
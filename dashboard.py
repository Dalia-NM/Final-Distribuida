import json
import time
import sys
import threading
import queue as _queue

import pika
import tqdm

# Importar la clase Baraja para mostrar la tabla de configuración
from deck import Baraja 

NUM_SIMULATIONS = 10000

GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
ENDC = '\033[0m'

try:
    import tkinter as tk
    from tkinter import ttk
    from tkinter import scrolledtext
    import matplotlib
    matplotlib.use('TkAgg') # Usar el backend de Tkinter
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    _HAS_GUI = True
except Exception:
    tk = None
    ttk = None
    Figure = None
    FigureCanvasTkAgg = None
    _HAS_GUI = False

class GuiDashboard:

    def __init__(self, total=NUM_SIMULATIONS):
        if not _HAS_GUI:
            raise RuntimeError('No hay soporte GUI')

        self.total = total
        self.root = tk.Tk()
        self.root.title('Simulacion BlackJack')

        # Estadísticas
        self.victories = 0
        self.defeats = 0
        self.ties = 0
        self.total_processed = 0

        # Mensaje de config
        self.baraja_config = None

        # Cola de mensajes del consumidor
        self.msg_q = _queue.Queue()

        main = ttk.Frame(self.root, padding=8)
        main.pack(fill='both', expand=True)

        left = ttk.Frame(main)
        left.pack(side='left', fill='y', padx=8)

        right = ttk.Frame(main)
        right.pack(side='right', fill='both', expand=True, padx=8)

        #Configuración y Log
        ttk.Label(left, text='Configuracion de Baraja', font=('TkDefaultFont', 12, 'bold')).pack(anchor='w')
        self.table = ttk.Treeview(left, columns=('valor', 'cantidad'), show='headings', height=14)
        self.table.heading('valor', text='Valor')
        self.table.heading('cantidad', text='Cantidad')
        self.table.column('valor', width=50, anchor='center')
        self.table.column('cantidad', width=80, anchor='center')
        self.table.pack(fill='y')

        # Contadores y Probabilidades
        stats_frame = ttk.Frame(left, padding=(0,12,0,0))
        stats_frame.pack(fill='x')
        self.stats_label = ttk.Label(stats_frame, text='V: 0  D: 0  E: 0  Total: 0')
        self.stats_label.pack()
        self.prob_label = ttk.Label(stats_frame, text='Probabilidades: V: 0.00%  D: 0.00%  E: 0.00%')
        self.prob_label.pack()

        # Log area
        log_frame = ttk.Frame(left)
        log_frame.pack(fill='both', expand=False, pady=(8,0))
        ttk.Label(log_frame, text='Log (ultimos resultados)').pack(anchor='w')
        self.log_widget = scrolledtext.ScrolledText(log_frame, height=10, width=40, wrap='none')
        self.log_widget.pack(fill='both', expand=True)
        self.log_widget.configure(state='disabled')


        # ------------------- Elementos Derecha (Gráfico Matplotlib) -------------------
        self.fig = Figure(figsize=(5,3))
        self.ax = self.fig.add_subplot(111)
        self.bars = self.ax.bar(['VICTORIA','DERROTA','EMPATE'], [0,0,0], color=['green','red','gold'])
        self.ax.set_ylim(0, 100)
        self.ax.set_ylabel('Porcentaje (%)')
        self.ax.set_title('Distribucion de resultados')
        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        self.canvas.get_tk_widget().pack(fill='both', expand=True)

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

        for i in self.table.get_children():
            self.table.delete(i)
        for v in Baraja.CARTAS_VALORES:
            self.table.insert('', 'end', values=(v, d.get(v,0)))

    def start(self):
        self._running = True
        self._consume_queue()
        self.root.mainloop()

    def _consume_queue(self):
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
        try:
            self.log_widget.configure(state='normal')
            self.log_widget.insert('end', f"Sim {result_data.get('sim_id')}: {res}\n")
            self.log_widget.see('end')
            self.log_widget.configure(state='disabled')
        except Exception:
            pass

    def _update_stats_widgets(self):
        self.stats_label.config(text=f'V: {self.victories}  D: {self.defeats}  E: {self.ties}  Total: {self.total_processed}')
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
        win_p = (self.victories/total)*100
        lose_p = (self.defeats/total)*100
        tie_p = (self.ties/total)*100
        self.prob_label.config(text=f'Probabilidades: V: {win_p:.2f}%  D: {lose_p:.2f}%  E: {tie_p:.2f}%')

    def final_report(self):
        if self.total_processed == 0:
            try:
                import tkinter.messagebox as mb
                mb.showinfo('No se recibieron resultados')
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

class Dashboard:
    def __init__(self, total: int = NUM_SIMULATIONS):
        self.victories = 0
        self.defeats = 0
        self.ties = 0
        self.total_processed = 0
        self.baraja_config = None
        self.total = total
        self.log_entries = []
        self.bar = tqdm(total=total, desc=f"{BLUE}Progreso de Simulación{ENDC}", unit="sim")

    def update_stats(self, result_data):
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

        if self.bar is not None:
            self.bar.update(1)
        
        sys.stdout.write(f"\r{color}[LOG]{ENDC} Sim ID {result_data['sim_id']}: {color}{result}{ENDC} | V: {GREEN}{self.victories}{ENDC} | D: {RED}{self.defeats}{ENDC} | E: {YELLOW}{self.ties}{ENDC} | Total: {self.total_processed}")
        sys.stdout.flush()

    def final_report(self):
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
        print(f"Victorias: {GREEN}{self.victories}{ENDC} ({win_prob:.2f}%)")
        print(f"Derrotas:  {RED}{self.defeats}{ENDC} ({lose_prob:.2f}%)")
        print(f"Empates:   {YELLOW}{self.ties}{ENDC} ({tie_prob:.2f}%)")
        print("-" * 60)
        print(f"{GREEN}PROBABILIDAD DE GANAR: {win_prob:.2f}%{ENDC}")
        print("="*60)
        self.print_chart(win_prob, lose_prob, tie_prob)

    def print_chart(self, win, lose, tie):
        print(f"\n{BLUE}Distribución de Resultados:{ENDC}")
        scale = 50 / 100
        win_bar = '#' * int(win * scale)
        lose_bar = '#' * int(lose * scale)
        tie_bar = '#' * int(tie * scale)
        print(f"Victoria: {GREEN}{win_bar}{ENDC} {win:.2f}%")
        print(f"Derrota:  {RED}{lose_bar}{ENDC} {lose:.2f}%")
        print(f"Empate:   {YELLOW}{tie_bar}{ENDC} {tie:.2f}%")

def run_dashboard():

    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    except Exception as e:
        print(f"No fue posible conectar a RabbitMQ")
        return

    channel = connection.channel()
    channel.queue_declare(queue='baraja', durable=True)
    channel.queue_declare(queue='resultados', durable=False)

    print("Esperando baraja...")
    method_frame, header_frame, body = channel.basic_get('baraja', auto_ack=True)
    while body is None:
        time.sleep(1)
        method_frame, header_frame, body = channel.basic_get('baraja', auto_ack=True)

    if isinstance(body, bytes):
        baraja_payload = body.decode('utf-8')
    else:
        baraja_payload = body
    use_gui = _HAS_GUI and not any(arg in ('--nogui', 'nogui') for arg in sys.argv)
    
    if use_gui:

        print("Iniciando Dashboard")
        gui = GuiDashboard(total=NUM_SIMULATIONS)
        gui.set_config(baraja_payload)

        consumer_thread = _start_consumer_thread_for_gui('localhost', 'resultados', gui)
        gui.start()
        gui.final_report()
        try:
            consumer_thread.join(timeout=0.1)
        except Exception:
            pass
        connection.close()
        return

    else:
        print("Iniciando Dashboard en modo Consola...")
        dashboard = Dashboard(total=NUM_SIMULATIONS)
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
            print("\nInterrumpido por el usuario.")
        finally:
            dashboard.final_report()
            connection.close()


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'dashboard'
    
    if mode in ('consumer', 'c'):
        sys.exit(1)
    else:
        run_dashboard()

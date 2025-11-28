import json
import random

# Configurar baraja
# Baraja de base clasica de poker
# 52 cartas con 4 ases, 12 figuras y 36 cartas numericas

class Baraja:

    CARTAS_VALORES = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
    VALORES_BASE = 4
    MAX_BASE = 52

    def __init__(self, *, VALORES_BASE: int = None, max_total: int = None, enforce_max: bool = True):
        
        default = self.VALORES_BASE if VALORES_BASE is None else VALORES_BASE
        self.config = {value: default for value in self.CARTAS_VALORES}

        self.MAX = self.MAX_BASE if max_total is None else max_total
        self.enforce_max = bool(enforce_max)

    def obtener_total(self):
        return sum(self.config.values())

    def modificar_cantidad(self, valor_carta, cantidad_nuevo):
        if valor_carta not in self.CARTAS_VALORES:
            print(f"Valor de carta '{valor_carta}' invalidoo.")
            return False

        if not isinstance(cantidad_nuevo, int) or cantidad_nuevo < 0:
            print(f"La cantidad debe ser un entero >= 0")
            return False

        total_actual = self.obtener_total()
        cantidad_actual = self.config[valor_carta]
        total_nuevo = total_actual - cantidad_actual + cantidad_nuevo

        if self.enforce_max and total_nuevo > self.MAX:
            print(f"El cambio de {valor_carta} a {cantidad_nuevo} excede el maximo permitido ({self.MAX})")
            return False

        self.config[valor_carta] = cantidad_nuevo
        print(f"Baraja modificada: {valor_carta} ahora tiene {cantidad_nuevo} cartas. Total actual: {total_nuevo}")
        return True

    def to_json(self):
        return json.dumps(self.config)

    @classmethod
    def from_json(cls, json_data):
        instance = cls()
        instance.config = json.loads(json_data)
        return instance

# --- Funciones de Lógica de Blackjack ---

def get_valor_carta(carta):
    if carta in ('J', 'Q', 'K'):
        return 10
    elif carta == 'A':
        return 11
    else:
        return int(carta)

def calcular_mano(mano):
    value = sum(get_valor_carta(carta) for carta in mano)
    num_aces = mano.count('A')
    
    # Ajustar el valor de los Ases de 11 a 1 si es necesario
    while value > 21 and num_aces > 0:
        value -= 10
        num_aces -= 1
        
    return value

def simulate_blackjack(baraja_config):
    #Crear una baraja para la simulación
    deck = []
    for card_value, count in baraja_config.items():
        deck.extend([card_value] * count)
        
    random.shuffle(deck)

    #Repartir manos
    try:
        # Se extraen 4 cartas para jugador y dealer
        player_hand = [deck.pop(), deck.pop()]
        dealer_hand = [deck.pop(), deck.pop()]
    except IndexError:
        return "ERROR_NO_CARTAS" 
    
    #Turno del Jugador (Pide hasta 17 o se pasa)
    while calcular_mano(player_hand) < 17:
        try:
            player_hand.append(deck.pop())
        except IndexError:
            break
            
    player_score = calcular_mano(player_hand)
    
    if player_score > 21:
        return "DERROTA"

    #Turno del Crupier (Pide hasta 17 o se pasa)
    dealer_score = calcular_mano(dealer_hand)
    while dealer_score < 17:
        try:
            dealer_hand.append(deck.pop())
            dealer_score = calcular_mano(dealer_hand)
        except IndexError:
            break

    if dealer_score > 21:
        return "VICTORIA"

    #Comparar resultados
    if player_score > dealer_score:
        return "VICTORIA"
    elif player_score < dealer_score:
        return "DERROTA"
    else:
        return "EMPATE"

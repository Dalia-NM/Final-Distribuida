import json
#Configurar baraja
# Baraja de base clasica de poker
# 52 cartas con 4 ases, 12 figuras y 36 cartas numericas
# 4 cartas de cada valor (A,2,3,4,5,6,7,8,9,10,J,Q,K)

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

    def modificar_varias(self, cambios: dict, allow_partial=False):
        # Validar entradas
        invalido= [k for k in cambios.keys() if k not in self.CARTAS_VALORES]
        if invalido:
            print(f"Valores invalidos en cambios: {invalido}")
            return ([], list(cambios.keys()))

        for k, v in cambios.items():
            if not isinstance(v, int) or v < 0:
                print(f"Valor invalido para {k}: {v} (debe ser int >= 0)")
                return ([], list(cambios.keys()))

        # Calcular nuevo total si aplicamos todos
        total_actual = self.obtener_total()
        nuevo_total = total_actual
        for k, v in cambios.items():
            nuevo_total += (v - self.config[k])

        if self.enforce_max and nuevo_total > self.MAX:
            if not allow_partial:
                print(f"El cambio rechazado: el total propuesto {nuevo_total} excede MAX {self.MAX}")
                return ([], list(cambios.keys()))
            # Si permitimos parcial, aplicamos solo los que no causen overflow
            applied = []
            rejected = []
            for k, v in cambios.items():
                tentative_total = self.obtener_total() + (v - self.config[k])
                if tentative_total <= self.MAX:
                    self.config[k] = v
                    applied.append(k)
                else:
                    rejected.append(k)
            print(f"Parcial aplicado: {applied}. Rechazados: {rejected}")
            return (applied, rejected)
#Aplicar todos los cambios
        for k, v in cambios.items():
            self.config[k] = v

        print(f"Cambios aplicados: {list(cambios.keys())}. Total ahora: {self.obtener_total()}")
        return (list(cambios.keys()), [])

    def set_max(self, new_max):
        if new_max is None:
            self.MAX = None
            self.enforce_max = False
            print("Limite de total desactivado (MAX = None)")
            return
        if not isinstance(new_max, int) or new_max < 0:
            print("new_max debe ser un entero >= 0 o None")
            return
        self.MAX = new_max
        print(f"Nuevo MAX establecido {self.MAX}")

    #Formato JSON
    def to_json(self):
        return json.dumps(self.config)

    #Crear baraja desde JSON
    @classmethod
    def from_json(cls, json_data):
        instance = cls()
        instance.config = json.loads(json_data)
        return instance

#Conversion de valores para figuras y ases

def get_valor_carta(carta):
    if carta in ('J', 'Q', 'K'):
        return 10
    elif carta == 'A':
        return 11
    else:
        return int(carta)

#Calcula valor de la mano

def calcular_mano(mano):
    value = sum(get_valor_carta(carta) for carta in mano)
    num_aces = mano.count('A')
    # Ajustar el valor de los Ases de 11 a 1 si es necesario
    while value > 21 and num_aces > 0:
        value -= 10
        num_aces -= 1
        
    return value
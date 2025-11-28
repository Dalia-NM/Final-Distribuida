# Descripción de los elementos del proyecto y orden de ejecución

## deck.py
Define la clase baraja que es utilizada por los demás programas para poder realizar las simulaciones, además de contener
la lógica matemática del juego.

## pro.py
Inicializa la simulación de los 10000 juegos establecidos y publica en la respectiva cola la configuración de la baraja.

## consumidor.py
Recibe el mensaje de cada escenario y lo procesa usando la lógica del black jack enviando los resultados a la cola
de resultados en el broker.

## dashboard.py
Muestra de forma gráfica el progreso de la ejecucion del sistema en tiempo real, obtiene la infromación de la cola
de resultados llenada por consumidor.py para poder mostrarlo e ir calculando la probabilidad aproximada.

## publicar.py 
No es escencial para que funcione el proyecto, ya que solo permite configurar la baraja de una forma más simple
mostrando directamente el formato json.

# Orden de ejecución
- Configura la baraja y luego ejecuta publicar.py
-  consumidor.py para que esté listo en espera
-  dashboard.py para poder apreciar el proceso
-  pro.py para iniciar la simulación

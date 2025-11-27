# Final-Distribuida
Código del proyecto final de Programación distribuida
## Descripción
Implementar un sistema que permita realizar una simulación Montecarlo de forma distribuida, utilizando el modelo de paso de mensajes. 
El sistema deberá tener un único productor que genere escenarios únicos a partir de un modelo proporcionado en un archivo de texto y
los publique en un bróker de mensajes (utilice RabbitMQ). 

El modelo puede ser cualquier función y las variables involucradas pueden tener diferentes funciones de distribución de probabilidad
para el rango de valores que pueden tener.  
El productor también deberá publicar la función que los consumidores deberán ejecutar en una cola específica, la política será
time-out delivery  y la caducidad será cuando se cargue otro modelo. 

Los consumidores deberán 

1. leer el modelo de la cola de modelo (una vez)
2. obtener un escenario de la cola de escenarios,
3. ejecutar el modelo
4.publicar su resultado en una cola de resultados.

Debe haber otro proceso visualizador (dashboard) que se encargue ir mostrado el avance de la simulación de forma gráfica en tiempo real,
tanto las estadísticas del productor como de cada uno de los clientes. 
Todos los componentes del sistema deben ejecutarse en diferentes equipos, la programación debe apegarse al paradigma orientado a objetos. 

## Especificaciones
Para este proyecto se pensó utilizar el método Montecarlo en la simulación del juego BlackJack y poder determinar la probabilidad de
ganr, esto con el factor adicional que se puede configurar la baraja de diferentes maneras, asi como cambiar la cantidad de simulaciones,
siendo 10000 las configuradas por defecto.
En la parte de la baraja de poker se usa la de poker con 52 cartas sin jokers y con 4 cartas de cada valor.

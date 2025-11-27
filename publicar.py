
import pika, json

config = {
  "A": 4, "2": 4, "3": 4, "4": 4, "5": 4,
  "6": 4, "7": 4, "8": 4, "9": 4, "10": 4,
  "J": 4, "Q": 4, "K": 4
}

conn = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
ch = conn.channel()
ch.queue_declare(queue='baraja', durable=True)
ch.basic_publish(exchange='', routing_key='baraja', body=json.dumps(config))
print("Publicado config en 'baraja'")
conn.close()
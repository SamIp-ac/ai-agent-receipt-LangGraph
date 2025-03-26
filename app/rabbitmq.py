import pika
import json
from app.agent import LangGraphAgent
from app.models import ImageRequest, ImageResponse
import logging
import os

class RabbitMQClient:
    def __init__(self):
        
        self.connection = None
        self.channel = None

    def connect(self, host='rabbitmq'):
        credentials = pika.PlainCredentials(
            username=os.getenv("RABBITMQ_USER", "admin"),
            password=os.getenv("RABBITMQ_PASS", "securepassword")
        )
        parameters = pika.ConnectionParameters(
            host=host,
            credentials=credentials,
            heartbeat=600,
            blocked_connection_timeout=300,
            connection_attempts=5
        )
        
        self.connection = pika.BlockingConnection(parameters)
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue='image_requests', durable=True)
        self.channel.queue_declare(queue='image_responses', durable=True)

    def publish_image_task(self, request: ImageRequest):
        self.channel.basic_publish(
            exchange='',
            routing_key='image_requests',
            body=request.model_dump_json(),
            properties=pika.BasicProperties(delivery_mode=2)  # Persistent
        )

    def start_consuming(self):
        def callback(ch, method, properties, body):
            try:
                request = ImageRequest.model_validate_json(body) ###
                json_data = self.agent.process_image(request.image_url)
                
                response = ImageResponse(
                    conversation_id=request.conversation_id,
                    json_data=json.loads(json_data)
                    )
                
                ch.basic_publish(
                    exchange='',
                    routing_key='image_responses',
                    body=response.model_dump_json()
                )
            except Exception as e:
                logging.error(f"Processing failed: {e}")

        self.channel.basic_consume(
            queue='image_requests',
            on_message_callback=callback,
            auto_ack=True
        )
        self.channel.start_consuming()
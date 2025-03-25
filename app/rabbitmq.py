import pika
import json
from app.agent import LangGraphAgent
from app.models import ChatRequest
import logging
import os

class RabbitMQClient:
    def __init__(self):
        self.agent = LangGraphAgent()
        self.connection = None
        self.channel = None
    
    # def connect(self, host='rabbitmq'):
    #     self.connection = pika.BlockingConnection(
    #         pika.ConnectionParameters(host=host))
    #     self.channel = self.connection.channel()
        
    #     # Declare queues
    #     self.channel.queue_declare(queue='chat_requests')
    #     self.channel.queue_declare(queue='chat_responses')

    # def connect(self, host='rabbitmq'):
    #     credentials = pika.PlainCredentials(
    #         username=os.getenv("RABBITMQ_USER", "admin"),
    #         password=os.getenv("RABBITMQ_PASS", "securepassword")
    #     )
    #     self.connection = pika.BlockingConnection(
    #         pika.ConnectionParameters(
    #             host=host,
    #             credentials=credentials,
    #             heartbeat=600,
    #             blocked_connection_timeout=300
    #         )
    #     )

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
            connection_attempts=5,  # Add retry attempts
            retry_delay=5  # Add delay between attempts
        )
        
        try:
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            self.channel.queue_declare(queue='chat_requests')
            self.channel.queue_declare(queue='chat_responses')
            logging.info("RabbitMQ connection established")
        except Exception as e:
            logging.error(f"RabbitMQ connection failed: {e}")
            raise
        
    def start_consuming(self):
        self.channel.basic_consume(
            queue='chat_requests',
            on_message_callback=self.process_request,
            auto_ack=True)
        
        logging.info("Waiting for messages. To exit press CTRL+C")
        self.channel.start_consuming()
    
    def process_request(self, ch, method, properties, body):
        try:
            request_data = json.loads(body)
            request = ChatRequest(**request_data)
            
            # Process with LangGraph agent
            response = self.agent.process_message(request.message)
            
            # Send response
            self.send_response(
                conversation_id=request.conversation_id,
                message=response
            )
        except Exception as e:
            logging.error(f"Error processing message: {e}")
    
    def send_response(self, conversation_id: str, message: str):
        if not self.channel:
            raise RuntimeError("RabbitMQ channel not initialized")
        
        response = {
            "conversation_id": conversation_id,
            "message": message
        }
        
        self.channel.basic_publish(
            exchange='',
            routing_key='chat_responses',
            body=json.dumps(response)
        )
    
    def close(self):
        if self.connection and not self.connection.is_closed:
            self.connection.close()
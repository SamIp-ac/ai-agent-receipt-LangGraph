import pika
import json
import logging
import os
import time
from typing import Optional, Callable

class RabbitMQClient:
    def __init__(self):
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[pika.adapters.blocking_connection.BlockingChannel] = None
        self._shutdown_listeners = []
        self._connection_params = None
        self._should_reconnect = True
        self._reconnect_delay = 5
        self._consuming = False

    def add_shutdown_listener(self, callback: Callable[[str], None]):
        self._shutdown_listeners.append(callback)

    def _notify_shutdown(self, reason: str):
        for listener in self._shutdown_listeners:
            try:
                listener(reason)
            except Exception as e:
                logging.error(f"Shutdown listener error: {e}")

    def connect(self, host='rabbitmq'):
        credentials = pika.PlainCredentials(
            username=os.getenv("RABBITMQ_USER", "admin"),
            password=os.getenv("RABBITMQ_PASS", "securepassword")
        )
        self._connection_params = pika.ConnectionParameters(
            host=host,
            credentials=credentials,
            heartbeat=600,
            blocked_connection_timeout=300,
            connection_attempts=5,
            retry_delay=5
        )
        
        try:
            self.connection = pika.BlockingConnection(self._connection_params)
            self.channel = self.connection.channel()
            
            # For BlockingConnection, we need to check for closures differently
            if not self.connection.is_open:
                raise pika.exceptions.AMQPConnectionError("Connection not open after creation")
                
            self.channel.queue_declare(queue='image_requests', durable=True)
            self.channel.queue_declare(queue='image_responses', durable=True)
            
            logging.info("Successfully connected to RabbitMQ")
            return True
            
        except Exception as e:
            logging.error(f"Connection failed: {e}")
            self._notify_shutdown(f"Connection failed: {str(e)}")
            return False

    def _check_connection(self):
        """Check if connection is still valid"""
        if not self.connection or not self.connection.is_open:
            self._notify_shutdown("Connection lost")
            return False
        return True

    def publish_image_task(self, request):
        if not self._check_connection():
            if not self._reconnect():
                raise ConnectionError("Cannot publish - no active RabbitMQ connection")

        try:
            self.channel.basic_publish(
                exchange='',
                routing_key='image_requests',
                body=request.model_dump_json(),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    content_type='application/json'
                ),
                mandatory=True
            )
            return True
        except pika.exceptions.AMQPError as e:
            logging.error(f"AMQP error during publish: {e}")
            self._notify_shutdown(f"Publish error: {str(e)}")
            return False

    def _reconnect(self):
        """Attempt to reconnect to RabbitMQ"""
        logging.info(f"Attempting to reconnect in {self._reconnect_delay} seconds...")
        time.sleep(self._reconnect_delay)
        try:
            self.close()  # Clean up any existing connection
            return self.connect()
        except Exception as e:
            logging.error(f"Reconnect failed: {e}")
            return False

    def close(self):
        """Cleanly close the connection"""
        self._should_reconnect = False
        try:
            if hasattr(self, 'channel') and self.channel and self.channel.is_open:
                self.channel.close()
            if hasattr(self, 'connection') and self.connection and self.connection.is_open:
                self.connection.close()
        except Exception as e:
            logging.error(f"Error during shutdown: {e}")
        finally:
            self.channel = None
            self.connection = None

    def __del__(self):
        self.close()

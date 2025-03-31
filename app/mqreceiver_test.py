import pika
import json
import logging
from typing import Optional, Callable, Any
import time

class RabbitMQReceiver:
    def __init__(self, queue_name: str):
        self.queue_name = queue_name
        self.connection = None
        self.channel = None
        self._should_stop = False

    def connect(self, host='localhost'):  # 'localhost': From Host to Docker Container:, 'rabbitmq': Docker-to-Docker Communication
        """Establish connection to RabbitMQ"""
        try:
            self.connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=host,
                    credentials=pika.PlainCredentials('admin', 'securepassword'),
                    heartbeat=600,
                    blocked_connection_timeout=300
                )
            )
            self.channel = self.connection.channel()
            self.channel.queue_declare(queue=self.queue_name, durable=True)
            logging.info(f"Connected to RabbitMQ and listening on queue '{self.queue_name}'")
            return True
        except Exception as e:
            logging.error(f"Connection failed: {e}")
            return False

    def start_consuming(self, callback: Optional[Callable] = None):
        """Start consuming messages with a callback"""
        if not self.connect():
            raise ConnectionError("Failed to connect to RabbitMQ")

        def _wrapped_callback(ch, method, properties, body):
            try:
                message = json.loads(body.decode('utf-8'))
                logging.info(f"Received message on {self.queue_name}:")
                # logging.info(json.dumps(message, indent=2))
                
                if callback:
                    callback(message)
            except json.JSONDecodeError:
                logging.info(f"Received non-JSON message: {body.decode('utf-8')}")
            except Exception as e:
                logging.error(f"Error processing message: {e}")

        self.channel.basic_consume(
            queue=self.queue_name,
            on_message_callback=_wrapped_callback,
            auto_ack=True
        )

        logging.info(f"Starting consumer for queue '{self.queue_name}'...")
        try:
            while not self._should_stop:
                self.connection.process_data_events(time_limit=1)  # Non-blocking
        except KeyboardInterrupt:
            logging.info("Consumer stopped by user")
        except Exception as e:
            logging.error(f"Consumer error: {e}")
        finally:
            self.close()

    def get_messages(self, count=1, timeout=5):
        """Get multiple messages with timeout"""
        if not self.connect():
            raise ConnectionError("Failed to connect to RabbitMQ")

        messages = []
        start_time = time.time()
        
        while len(messages) < count and (time.time() - start_time) < timeout:
            method_frame, _, body = self.channel.basic_get(
                queue=self.queue_name,
                auto_ack=True
            )
            if method_frame:
                try:
                    messages.append(json.loads(body.decode('utf-8')))
                except json.JSONDecodeError:
                    messages.append(body.decode('utf-8'))
        
        return messages

    def stop(self):
        """Gracefully stop the consumer"""
        self._should_stop = True

    def close(self):
        """Clean up resources"""
        try:
            if self.channel and self.channel.is_open:
                self.channel.close()
            if self.connection and self.connection.is_open:
                self.connection.close()
        except Exception as e:
            logging.error(f"Error closing connection: {e}")
        finally:
            self.channel = None
            self.connection = None

def process_message(message):
    """Custom message processor"""
    if 'json_data' in message:
        try:
            receipt = message['json_data']
        except:
            receipt = message['text']

        print(f"\nReceipt Details for {message['conversation_id']}:")
        # print(f"Store: {receipt.get('store')}")
        # print(f"Total: ${receipt.get('total', 0):.2f}")
        # print(f"Items: {len(receipt.get('items', []))}")
        print(f"All: {receipt}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
    
    # For response messages
    receiver = RabbitMQReceiver(queue_name='image_responses')
    
    try:
        # Start consuming with custom processor
        receiver.start_consuming(callback=process_message)
    except KeyboardInterrupt:
        receiver.stop()
import pika
from app.rabbitmq import RabbitMQClient
from app.agent import LangGraphAgent
from app.models import ImageRequest, ImageResponse
import logging
import json
import time

class Worker:
    def __init__(self):
        self.rabbitmq_client = RabbitMQClient()
        self.agent = LangGraphAgent()
        self.rabbitmq_client.add_shutdown_listener(self._handle_shutdown)
        self._running = True

    def _handle_shutdown(self, reason: str):
        logging.error(f"RabbitMQ connection lost: {reason}")
        self._running = False

    def callback(self, ch, method, properties, body):
        try:
            request = ImageRequest.model_validate_json(body)
            logging.info(f"Processing image (Size: ~{len(request.image_url)//1024}KB)")
            
            json_data = self.agent.process_image(request.image_url)
            response = ImageResponse(
                conversation_id=request.conversation_id,
                json_data=json.loads(json_data)
            )
            
            if not self.rabbitmq_client.publish_image_task(response):
                logging.error("Failed to publish response")
                
        except Exception as e:
            logging.error(f"Failed processing: {e}")
            error_response = {
                "error": str(e),
                "conversation_id": getattr(request, 'conversation_id', 'unknown')
            }
            try:
                self.rabbitmq_client.publish_image_task(error_response)
            except Exception as pub_err:
                logging.error(f"Failed to publish error: {pub_err}")

    def run(self):
        logging.basicConfig(level=logging.INFO)
        while self._running:
            try:
                if not self.rabbitmq_client.connect():
                    time.sleep(5)
                    continue
                    
                self.rabbitmq_client.channel.basic_consume(
                    queue='image_requests',
                    on_message_callback=self.callback,
                    auto_ack=True
                )
                
                logging.info("Worker started - Waiting for image tasks")
                try:
                    self.rabbitmq_client.channel.start_consuming()
                except pika.exceptions.ConnectionClosedByBroker:
                    logging.error("Connection closed by broker")
                    continue
                except pika.exceptions.AMQPChannelError as err:
                    logging.error(f"Channel error: {err}")
                    continue
                except pika.exceptions.AMQPConnectionError:
                    logging.error("Connection was closed")
                    continue
                
            except KeyboardInterrupt:
                self._running = False
                logging.info("Worker shutting down...")
                break
            except Exception as e:
                logging.critical(f"Unexpected error: {e}")
                time.sleep(5)  # Prevent tight loop on persistent errors
            finally:
                self.rabbitmq_client.close()

if __name__ == "__main__":
    Worker().run()
from app.rabbitmq import RabbitMQClient
from app.agent import LangGraphAgent  # Import agent directly
from app.models import ImageRequest
from redis import Redis
import logging
import json

class Worker:
    def __init__(self):
        self.redis = Redis(host="redis", port=6379, socket_connect_timeout=5)
        self.rabbitmq_client = RabbitMQClient()
        self.agent = LangGraphAgent()  # Initialize agent directly

    def callback(self, ch, method, properties, body):
        try:
            request = ImageRequest.model_validate_json(body)
            logging.info(f"Processing image (Size: ~{len(request.image_url)//1024}KB)")
            
            json_data = self.agent.process_image(request.image_url)
            result = json.loads(json_data)
            
            if "error" in result:
                raise ValueError(result["error"])
                
            response = {
                "conversation_id": request.conversation_id,
                "json_data": result,  # Already parsed JSON
                "status": "completed"
            }
            self.redis.setex(
                request.conversation_id,
                3600,
                json.dumps(response, ensure_ascii=False)
            )
            logging.info(f"Stored valid JSON for {request.conversation_id}")
            
        except Exception as e:
            logging.error(f"Failed processing: {str(e)}")
            self.handle_error(
                request.conversation_id if 'request' in locals() else "unknown",
                str(e)
            )

    def handle_error(self, conversation_id: str, error: str):
        error_response = {
            "conversation_id": conversation_id,
            "error": error,
            "status": "failed"
        }
        self.redis.setex(
            conversation_id,
            3600,
            json.dumps(error_response)
        )
        logging.error(f"Failed processing {conversation_id}: {error}")

    def run(self):
        logging.basicConfig(level=logging.INFO)
        try:
            self.rabbitmq_client.connect()
            self.rabbitmq_client.channel.basic_consume(
                queue='image_requests',
                on_message_callback=self.callback,
                auto_ack=True
            )
            logging.info("Worker started - Waiting for image tasks")
            self.rabbitmq_client.channel.start_consuming()
        except Exception as e:
            logging.critical(f"Worker startup failed: {e}")
        finally:
            if self.rabbitmq_client.connection:
                self.rabbitmq_client.close()
            self.redis.close()

if __name__ == "__main__":
    Worker().run()
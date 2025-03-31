from datetime import datetime
import pika
from app.rabbitmq import RabbitMQClient
from app.agent import LangGraphAgent
from app.models import ImageRequest, ImageRequestPrompt
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
            # 先判断消息类型
            logging.info(f"Processing image")
            raw_data = json.loads(body)
            
            if 'conversation_id' in raw_data and 'image_url' in raw_data:
                # 处理请求消息
                request = ImageRequestPrompt.model_validate(raw_data)
                self._process_image_request(request)
            elif 'conversation_id' in raw_data and 'json_data' in raw_data:
                # 处理响应消息（如果有）
                self._handle_response(raw_data)
            else:
                logging.error(f"Unknown message format: {raw_data.keys()}")
                
        except json.JSONDecodeError as e:
            logging.error(f"Invalid JSON: {str(e)[:200]}")
        except Exception as e:
            logging.error(f"Unexpected error: {type(e).__name__}: {str(e)[:200]}")
            if 'raw_data' in locals():
                logging.debug(f"Raw message: {raw_data}")

    def _process_image_request(self, request: ImageRequestPrompt):
        """专用方法处理图片请求"""
        try:
            # Log start of processing
            logging.info(f"Starting image processing for conversation: {request.conversation_id}")
            
            raw_output = self.agent.process_image(request.image_url, request.include_items)

            json_str = raw_output.strip().removeprefix("```json").removesuffix("```").strip()
            json_data = json.loads(json_str)
            
            # Log parsed data
            logging.info(f"Successfully processed receipt data for {request.conversation_id}:")
            
            response = {
                "conversation_id": request.conversation_id,
                "json_data": json_data,
                "status": "completed"
            }
            
            # Publish and log result
            if self.rabbitmq_client.publish(
                queue='image_responses',
                body=json.dumps(response)
            ):
                logging.info(f"Successfully published response for {request.conversation_id}")
            else:
                logging.error(f"Failed to publish response for {request.conversation_id}")
                
        except json.JSONDecodeError as e:
            error_msg = f"JSON parsing failed: {str(e)}"
            logging.error(f"{error_msg}. Raw data: {raw_output[:200]}...")
            self._publish_error(request.conversation_id, error_msg)
            
        except Exception as e:
            error_msg = f"Processing failed: {type(e).__name__}: {str(e)}"
            logging.error(error_msg)
            self._publish_error(request.conversation_id, error_msg)

    def _publish_error(self, conversation_id: str, error_msg: str):
        """统一错误发布方法"""
        error_data = {
            "conversation_id": conversation_id or "unknown",
            "error": error_msg[:500],  # 限制长度
            "timestamp": datetime.now().isoformat()
        }
        self.rabbitmq_client.publish(
            queue='image_errors',
            body=json.dumps(error_data))
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
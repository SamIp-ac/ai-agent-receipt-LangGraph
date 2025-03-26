# client.py
import pika
import json

def on_message(ch, method, properties, body):
    try:
        data = json.loads(body)
        if "error" in data:
            print(f"收到错误结果: {data['error']}")
        else:
            print(f"收到处理结果: {data}")
        # 手动确认消息（确保可靠性）
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        print(f"处理消息失败: {e}")

# 连接到 RabbitMQ
connection = pika.BlockingConnection(
    pika.ConnectionParameters(host='你的RabbitMQ服务器IP')
)
channel = connection.channel()

# 声明队列（确保存在）
channel.queue_declare(queue='image_respones', durable=True)

# 订阅队列
channel.basic_consume(
    queue='image_responses',
    on_message_callback=on_message,
    auto_ack=False  # 关闭自动确认，手动控制
)

print("客户端已启动，等待结果...")
channel.start_consuming()  # 阻塞监听
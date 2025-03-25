# ai-agent-receipt-LangGraph
ai-agent for receipt by LangGrap

ai-agent/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI application
│   ├── agent.py         # LangGraph agent
│   ├── rabbitmq.py      # RabbitMQ consumer/producer
│   ├── models.py        # Pydantic models
│   └── config.py        # Configuration
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env

### Env setup
```shell
conda create -n aiagent_langgraph_receipt312 python=3.12
conda activate aiagent_langgraph_receipt312
conda env update -f environment.yml
```
## Build the Docker images:
```shell
docker-compose build
```

## Start the services:
```shell
docker-compose up -d
```

## Use via..
### REST API
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"conversation_id": "123", "message": "Hello!"}'
```

### RabbitMQ
```json
{
  "conversation_id": "123",
  "message": "Hello AI!"
}
```

docker-compose up -d

### Test and Run
```shell
# Stop and remove old containers
docker-compose down -v

# Rebuild with fresh environment
docker-compose up --build -d --scale worker=2
```

# Terminal 1 - API
uvicorn app.main:app --reload

# Terminal 2 - Worker
python -m app.worker

http://localhost:8000/docs

docker-compose up --build -d --scale worker=2
docker-compose up -d --scale worker=2  # Scale workers
from langgraph.graph import StateGraph
from typing import TypedDict, List
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
import base64
import requests
import os

class AgentState(TypedDict):
    messages: List[BaseMessage]

class LangGraphAgent:
    def __init__(self):
        self.model = "gemma-3-4b-it"
        self.api_url = "http://host.docker.internal:1234/v1/chat/completions" # "http://localhost:1234/v1/chat/completions"
        self.workflow = self._create_workflow()
    
    def _create_workflow(self):
        workflow = StateGraph(AgentState)
        
        workflow.add_node("agent", self._agent_node)
        workflow.add_node("human", self._human_node)
        
        workflow.add_edge("agent", "human")
        workflow.add_edge("human", "agent")
        
        workflow.set_entry_point("agent")
        return workflow.compile()
    
    def _call_gemma(self, messages: List[dict], max_tokens: int = 1200, temperature: float = 0.1):
        """Helper method to call local Gemma model"""
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }
        
        response = requests.post(self.api_url, headers=headers, json=payload)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        raise Exception(f"Gemma API error: {response.status_code} - {response.text}")
    
    def _agent_node(self, state: AgentState):
        """Process messages through Gemma model"""
        last_message = state['messages'][-1]
        
        # Convert LangChain messages to Gemma format
        messages = [{
            "role": "user" if isinstance(msg, HumanMessage) else "assistant",
            "content": msg.content
        } for msg in state['messages']]
        
        response_content = self._call_gemma(messages)
        return {"messages": [AIMessage(content=response_content)]}
    
    def _human_node(self, state: AgentState):
        """Process human input (from RabbitMQ)"""
        last_message = state['messages'][-1].content
        return {"messages": [HumanMessage(content=last_message)]}
    
    def process_message(self, message: str):
        """Entry point for text processing"""
        initial_state = {"messages": [HumanMessage(content=message)]}
        result = self.workflow.invoke(initial_state)
        return result['messages'][-1].content
    
    def process_image(self, image_path: str, prompt: str):
        """Specialized method for image processing"""
        with open(image_path, "rb") as image_file:
            encoded_image = base64.b64encode(image_file.read()).decode("utf-8")
        
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded_image}"}}
                ]
            }
        ]
        
        response_content = self._call_gemma(messages)
        os.remove(image_path)  # Clean up temp file
        return response_content
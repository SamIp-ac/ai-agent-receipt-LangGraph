from langgraph.graph import StateGraph
from typing import TypedDict, List
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
import base64
import requests
import json
from app import system_prompt

class AgentState(TypedDict):
    messages: List[BaseMessage]
    should_continue: bool 

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
    
    def process_image(self, image_url: str) -> str:
        """Specialized image-to-JSON processor"""
        if image_url.startswith(('http://', 'https://')):
            # Download image
            img_data = requests.get(image_url).content
            encoded_image = base64.b64encode(img_data).decode('utf-8')
        else:
            # Assume base64
            encoded_image = image_url

        messages = [
            {
                "role": "system",
                "content": [{"type": "text", "text": system_prompt}]
                },
            {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded_image}"}},
                {"type": "text", "text": "Make sure all json item is totatlly correct and calculated. Just return Json"},
            ]
        }]
        
        try:
            response = self._call_gemma(messages)
            
            # Clean Markdown code blocks before validation
            cleaned_response = response.replace("```json", "").replace("```", "").strip()
            
            # Validate JSON
            json.loads(cleaned_response)  # Test if valid JSON
            return cleaned_response
            
        except json.JSONDecodeError:
            return json.dumps({
                "error": "AI response was not valid JSON", 
                "raw": response[:200]  # Truncate for logging
            })
    
    def get_single_response(self, message: str) -> str:
        """Direct single-response method without workflow"""
        messages = [{
            "role": "user",
            "content": message
        }]
        return self._call_gemma(messages)
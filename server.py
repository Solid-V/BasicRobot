from fastapi import FastAPI
from pydantic import BaseModel
from ollama import Client

app = FastAPI()
ollama_client = Client(host="YOUR IP:PORT") # replace with the ip at which you will host ollama so the port will always be 11434 unlesss you manually changed it


class Prompt(BaseModel):
    prompt: str

@app.post("/chat") #this is the endpoint you will use to send the prompt to the server and get a response back
async def chat(data: Prompt):
    try:
        response = ollama_client.chat(
            model="gemma3:4b", # replace with the model you want to use i changed it to llama3:7b becuase that worked better but you also need a better computer to run it
            messages=[{"role": "user", "content": data.prompt}],
        )

        message = response.get("message", {})
        role = message.get("role", "unknown")
        content = message.get("content", "No content found.")

        return {"role": role, "content": content}

    except Exception as e:
        return {"error": f"An error occurred: {str(e)}"}

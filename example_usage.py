from get_inference_service import InferenceServerManager
import asyncio
import subprocess
import os
import json

from openai import OpenAI


## let's say you want to use the InferenceServerManager class to get all of the available models
## you can do the following:
all_available_models_query = {
    "name": "",
    "quantization": "",
    "use_regex_model_name": False,
    "use_regex_quantization": False
}


def new_server_cb(model):
    print(f"New server available: {model}")
    ## here's where we could, for example, call a subprocess out to whatever other python script
    ## capture the output and print it to the console
    
    ## the base_url is the url we fetched from the NATS server
    client = OpenAI(base_url=model.get("url"), api_key="multiverse")
    print(model)
    
    ## now, in this function, you can actually send a request to the server to get the model
    completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Please tell me a joke about AIs"}
            ],
            model=model.get("name"),
            temperature=0.7,
        )
    ## do whatever you want with the completion
    content = completion.choices[0].message.content
    print(content)
    
    ## your code here...
    return content
    
def server_unavailable_cb(model):
    print(f"Server unavailable: {model}")
    ## your code to handle de-registering a server here...
    return


async def main():
    manager = InferenceServerManager(all_available_models_query)
    await manager.connect()
    await manager.listen_for_response(new_server_cb=new_server_cb, server_unavailable_cb=server_unavailable_cb)  # Listen for responses before we make requests
    await manager.update_servers()  # Initialize and make requests
    try:
        await asyncio.Future()  # Keep the loop running indefinitely
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        await manager.close()  # Properly close NATS connection

if __name__ == '__main__':
    
    asyncio.run(main())


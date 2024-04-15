import asyncio
from nats.aio.client import Client as NATS
from nats.aio.errors import ErrConnectionClosed, ErrTimeout, ErrNoServers
import json
import re
import signal
import sys
import dotenv
import requests 
import os
dotenv.load_dotenv()


our_models = [
    {
        "name": "TheBloke/Llama-2-70B-Chat-GGUF/llama-2-70b-chat.Q2_K.gguf", 
        "quantization": "Q2_K", 
        "ram": "64GB",
        "url": "https://b9a0-2601-1c2-100-ded-c1a3-69cc-cf1d-b34d.ngrok-free.app/v1", ## this is not a real url, use your cloudflare or ngrok url, or your cloud resource url
        "filename": "llama-2-70b-chat.Q2_K.gguf", ## if quantization is used, you'll have a specific thing,
        "loras": [{
            ## undefined schema for now
    
        }]
    }
    # Additional models go here
]

async def run_nats_client():
    # Establish a connection to the NATS server
    nats_client = NATS()
    nats_client_url = os.getenv("NATS_SERVER_URL", "nats://0.0.0.0:4222")
    await nats_client.connect(nats_client_url)

    async def announce_service():
        """Announce service availability and capabilities."""
        # Convert dict to JSON string if using json for message payload
        for model in our_models:
            await nats_client.publish("inference.available", json.dumps({
                "selected_model": model
                }).encode())
        print("announced service availability for models: ", our_models)
        
    async def announce_service_unavailability(model):
        """Announce that the service is no longer available."""
        # Implement service unavailability announcement
        if not model:
            await nats_client.publish("inference.unavailable", json.dumps(our_models).encode())
        else:
            await nats_client.publish("inference.unavailable", json.dumps([model]).encode())
        print("announced service unavailability for models: ", our_models)

    async def listen_for_requests():
        """Listen on 'inference.requested' and process inference requests."""
        async def request_handler(msg):
            subject = msg.subject
            data = json.loads(msg.data.decode())
            print(f"Received a request on '{subject}': {data}")
            requested_model = data
            # Reply to the request, if no specific model is requested, reply with any available model
            if data.get("name", "") == "":
                ## no model requested, reply with any available model from our_models
                selected_model = our_models[0]
            else:
                ## model requested, reply with the requested model
                matching_models= []
                selected_model = None
                ## do we have this model loaded?
                for model in our_models:
                    ## first filter out any models that don't match the requested model name
                    ## check if use_regex_model_name is set to True, if so match using regex, if not match using exact string match
                    if requested_model["use_regex_model_name"]:
                        if re.match(requested_model["name"], model["name"]):
                            matching_models.append(model)
                    else:
                        if requested_model.get("name") == model["name"]:
                            matching_models.append(model)
                            
                    ## check if the model has a quantization attribute with a value
                    
                    if requested_model.get("quantization") is None:
                        selected_model = matching_models[0]
                    ## if we have a match, check if the model is quantized
                    if len(matching_models) > 0:
                        ## get the first model that matches the requested quantization
                        for model in matching_models:
                            ## check if use_regex_quantization is set to True, if so match using regex, if not match using exact string match
                            if requested_model["use_regex_quantization"]:
                                if re.match(requested_model["quantization"], model["quantization"]):
                                    selected_model = model
                            else:
                                if requested_model["quantization"] == model["quantization"]:
                                    selected_model = model
            if selected_model is None:
                return 
            else:
                reply = json.dumps({
                    "requested_model": requested_model,
                    "selected_model": selected_model
                })
                await nats_client.publish("inference.available", reply.encode())
                print(f"Published a message on 'inference.available': {reply}")

        # Subscribe to the channel
        await nats_client.subscribe("inference.requested", cb=request_handler)

    async def periodic_health_check():
        """Periodically check the health of the service and re-announce if necessary."""
        while True:
            ## ping every model
            for model in our_models:
                model_url = model["url"]
                ## it's the baseurl of the model, you can check /models endpoint to see if the model is healthy
                try:
                    response = requests.get(f"{model_url}/models")
                    response.raise_for_status()
                    
                    response_json = response.json()
                    response_json = response_json.get("data", {})
                    ## you can get a list of models loaded on the server from this url
                    ## you could dynamically check add all of the models to the list above
                    ## but I've left that as an exercise for you to figure out
                    print(f"Model health check response: {response_json}")
                ## if the model is not healthy, announce the service unavailability
                except requests.exceptions.RequestException as e:
                    print(f"Error checking model health: {e}")
                    ## announce that the model is no longer available
                    await announce_service_unavailability(model)
                
            await asyncio.sleep(60 * 5)  # Check every 5 minutes

    # Announce service availability at startup
    await announce_service()

    # Start listening for inference requests
    await listen_for_requests()
    
    
    
    ## when the script exits, announce that the service is no longer available
    ## this is a good practice to let the clients know that the service is no longer available
    ## and they should look for another service
    ## you can do this by adding a signal handler for SIGTERM or SIGINT
    async def signal_handler(sig, frame):
        print("Service is shutting down")
        ## announce on the inference.available channel that the service is no longer available
        await announce_service_unavailability()
        await nats_client.close()
        sys.exit(0)
        
    
        
    ## add a signal handler for SIGTERM or SIGINT to announce that the service is no longer available
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


    # Start periodic health checks
    asyncio.create_task(periodic_health_check())

    # Keep the service running
    while True:
        await asyncio.sleep(3600)  # Keep the connection alive
    
    
        
if __name__ == '__main__':
    asyncio.run(run_nats_client())









    

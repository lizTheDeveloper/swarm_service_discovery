## ask for a service name and return the service object
import json
import re
import os
from nats.aio.client import Client as NATS    

class InferenceServerManager:
    def __init__(self, config):
        self.config = config
        self.models = []
        nats_client_url = os.getenv("NATS_SERVER_URL", "nats://0.0.0.0:4222")
        self.nats_client = None
        self.nats_server = nats_client_url
    
    def get_models(self):
        return self.models
    
    async def connect(self):
        if not self.nats_client:
            self.nats_client = NATS()
            print("Connecting to NATS server: ", self.nats_server)
            await self.nats_client.connect(self.nats_server)
            print("connected to NATS server: ", self.nats_server)
        
    async def update_servers(self):
        """
        Issues a request to the service discovery service to get the latest list of available servers.
        """
        if not self.nats_client and not self.nats_client.is_connected:
            self.connect()
        # Request the model service
        print("Requesting models: ", self.config)
        await self.nats_client.publish("inference.requested", json.dumps(self.config).encode())
        
        print("Requested models: ", self.config)
            
    async def handle_service_unavailability(self, models, server_unavailable_cb=None):
        """
        Listens for the inference.unavailable message and updates the list of available servers.

        Args:
            models (list): List of models that are no longer available.
        """
        for model in models:
            for known_model in self.models:
                if known_model["url"] == model["url"]:
                    self.models.remove(known_model)
                    if server_unavailable_cb:
                        await server_unavailable_cb(model)
        

    async def listen_for_response(self, new_server_cb=None, server_unavailable_cb=None):
        """
        Listens for the inference.available message and updates the list of available servers.
        """
        print("Listening for available models")
        print(new_server_cb)
        print(server_unavailable_cb)
        async def available_handler(msg):
            print("Received models: ", msg.data.decode())
            models = json.loads(msg.data.decode())
            if models.get("requested_model"):
                model = models.get("selected_model")
                valid = self.add_model(model)
                if valid and new_server_cb:
                    await new_server_cb(model)
        print("Listening for available models")
        await self.nats_client.subscribe("inference.available", cb=available_handler)
        print("Subscribed to inference.available")
        ## listen to the response on inference.unavailable
        async def unavailable_handler(msg):
            models = json.loads(msg.data.decode())
            await self.handle_service_unavailability(models, server_unavailable_cb)
        
        print("Listening for unavailable models")
        await self.nats_client.subscribe("inference.unavailable", cb=unavailable_handler)
        print("Subscribed to inference.unavailable")
        
    async def close(self):
        await self.nats_client.close()
        print("Closed connection to NATS server")
        
    def add_model(self, model):
        ## make sure it matches our requested config
        ## if the model wasn't empty, check if the model name matches
        
        if self.config["name"] != "":
            ## check if we're using regex match
            if self.config["use_regex_model_name"]:
                if not re.match(self.config["name"], model["name"]):
                    return False
            else:
                if self.config["name"] != model["name"]:
                    return False
        ## if the quantization wasn't empty, check if the quantization matches
        if self.config["quantization"] != "":
            ## check if we're using regex match
            if self.config["use_regex_quantization"]:
                if not re.match(self.config["quantization"], model["quantization"]):
                    return False
            else:
                if self.config["quantization"] != model["quantization"]:
                    return False
        self.models.append(model)
        return True
        
    
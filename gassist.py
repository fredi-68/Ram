#Discord ProtOS Bot
#
#Author: fredi_68
#
#Google assistant integration for ProtOS Discord Bot

import logging
import json

import google.oauth2.credentials
import google.auth.transport.requests
import google.auth.transport.grpc
from google.assistant.embedded.v1alpha2 import embedded_assistant_pb2, embedded_assistant_pb2_grpc

CREDENTIALS_PATH = "config/google_assistant_credentials.json"
DEADLINE = 60 * 3 + 5 #dunno what this means

class GoogleAssistant():

    logger = logging.getLogger("AI/GASSIST")

    def __init__(self, config):

        """
        Google Assistant integration.
        This class manages the connection to the Google Assistant API
        """

        self.language = "en-US"
        self.deviceID = ""
        self.modelID = ""
        self.loadConfig(config)

        f = open(CREDENTIALS_PATH, "r")
        self.credentials = google.oauth2.credentials.Credentials(token=None, **json.load(f))
        f.close()

        try:
            req = google.auth.transport.requests.Request()
            self.credentials.refresh(req)
        except:
            self.logger.error("Google Cloud API credentials validation failed.")

        self.grpc_channel = google.auth.transport.grpc.secure_authorized_channel(self.credentials, req, 'embeddedassistant.googleapis.com')

        self.conversation_state = None
        self.gassistInstance = embedded_assistant_pb2_grpc.EmbeddedAssistantStub(self.grpc_channel)

    def loadConfig(self, config):

        try:
            self.deviceID = config.getElementText("google.assistant.deviceID")
            self.modelID = config.getElementText("google.assistant.modelID")
        except:
            self.logger.error("An error occured while accessing the config data for Google Assistant: ")
            self.logger.exception()
            return False

        if not (self.deviceID and self.modelID):
            self.logger.error("Google Assistant is not properly configured. Check your config file!")
            return False

        self.logger.debug("Config loaded.")
        return True

    def getTextResponse(self, query):

        """
        Send a query to the Google Assistant API and return the result.
        """

        self.logger.debug("Sending conversation query...")

        def iter_requests():
            dialog_state = embedded_assistant_pb2.DialogStateIn(language_code=self.language, conversation_state = self.conversation_state or b"")

            audio_config = embedded_assistant_pb2.AudioOutConfig(encoding="LINEAR16", sample_rate_hertz=16000, volume_percentage=0)
            device_config = embedded_assistant_pb2.DeviceConfig(device_id=self.deviceID, device_model_id=self.modelID)

            config = embedded_assistant_pb2.AssistConfig(audio_out_config = audio_config, dialog_state_in = dialog_state, device_config = device_config, text_query = query)
            req = embedded_assistant_pb2.AssistRequest(config=config)
            yield req

        return_text = ""
        for resp in self.gassistInstance.Assist(iter_requests(), DEADLINE):

            self.conversation_state = resp.dialog_state_out.conversation_state or self.conversation_state
            return_text = resp.dialog_state_out.supplemental_display_text or return_text

        self.logger.debug("Got result: "+return_text)

        return return_text
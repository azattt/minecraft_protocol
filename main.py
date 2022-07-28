import threading
import time
from protocol import protocol_47
from protocol.protocol_types import String, VarInt
from protocol.constants import *


def map_handler(event):
    print(time.time(), event["type"])
    pass


def chat_handler(chat):
    print(chat)


def spam():
    while True:
        protocol_client.send_packet(0x01,
                                    String(str(time.time())),
                                    compress=False)
        time.sleep(0.01)


def state_handler(state):
    if state["state"] == STATE_PLAY:
        spam_thread = threading.Thread(target=spam, daemon=True)
        spam_thread.start()


protocol_client = protocol_47.ProtocolClient()
#protocol_client.set_map_handler(map_handler)
protocol_client.set_chat_handler(chat_handler)
protocol_client.set_state_handler(state_handler)
protocol_client.create_connection(("localhost", 25565))
protocol_client.login_as("CoolSeymur1")

while True:
    cmd_input = input().split()
    if cmd_input[0] == "chat":
        protocol_client.send_packet(0x01,
                                    String(" ".join(cmd_input[1:])),
                                    compress=False)

protocol_client.join_threads()

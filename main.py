import curses
from protocol import protocol_47


def map_handler(event):
    print(event)


def chat_handler(chat):
    print(chat)


def state_handler(state):
    print(state)


protocol_client = protocol_47.ProtocolClient()
protocol_client.set_map_handler(map_handler)
protocol_client.set_chat_handler(chat_handler)
protocol_client.set_state_handler(state_handler)
protocol_client.create_connection(("localhost", 25565))
protocol_client.login_as("CoolSeymur")
while True:
    pass
protocol_client.join_threads()

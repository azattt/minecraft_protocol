import json
import socket
import threading
from typing import Callable
import zlib
from protocol.protocol_types import (
    String, UShort, VarInt, parse_NBT_stream, parse_entity_metadata,
    read_Angle, read_Boolean, read_Byte, read_Chat, read_Double, read_Float,
    read_Int, read_Long, read_Position, read_Short, read_Slot, read_String,
    read_UByte, read_UUID, read_VarInt)


def print(*args, **kwargs):
    pass


HANDSHAKE_LOGIN = 2
HANDSHAKE_STATUS = 1
STATE_DISCONNECT = -1
STATE_LOGIN = 0
STATE_PLAY = 1
ACTION_ADD_PLAYER = 0
ACTION_UPDATE_GAMEMODE = 1
ACTION_UPDATE_LATENCY = 2
ACTION_UPDATE_DISPLAY_NAME = 3
ACTION_REMOVE_PLAYER = 4
ENTER_COMBAT = 0
END_COMBAT = 1
ENTITY_DEAD = 2
LOG_TIME_UPDATES = 0


class ProtocolClient:
    """Minecraft Protocol Client class"""

    def __init__(self) -> None:
        self.socket: socket.socket = None
        self.data_buf = b""
        self.packets = []
        self.packets_1 = []
        self.packets_2 = []
        self.compression_enabled = False
        self.state = STATE_LOGIN
        self.info = {}
        self.receive_data_thread: threading.Thread = None
        self.process_data_thread: threading.Thread = None
        self.connected = False

        self.map_handler: Callable = None
        self.chat_handler: Callable = None
        self.state_handler: Callable = None

    def create_connection(self, address: tuple[str, int]) -> int:
        """create connection"""
        if not self.socket:
            self.socket = socket.socket()
        else:
            if self.is_connected():
                raise RuntimeError(
                    "Client is still connected. Please disconnect.")

        self.socket.connect(address)
        self.connected = True

    def is_connected(self) -> bool:
        """checks whether socket is still connected or not"""
        if not self.socket:
            raise RuntimeError("Socket not created")
        return self.connected

    def close_connection(self):
        """closes socket"""
        self.socket.close()

    def send_packet(self, packet: bytes, compression: bool = False):
        """send packet. blocking"""
        if compression:
            raise NotImplementedError()
        if not self.is_connected():
            raise RuntimeError("Trying to send packet nowhere")
        self.socket.sendall(VarInt(len(packet)) + packet)

    def handle_plugin_message(self, data: bytes) -> int:
        """ Handling minecraft plugin messages"""
        channel, pointer = read_String(data)
        print(channel)
        if channel == "MC|Brand":
            self.info["host_brand"], _ = read_String(data, pointer)
        return 0

    def set_map_handler(self, handler: Callable):
        self.map_handler = handler

    def set_chat_handler(self, handler: Callable):
        self.chat_handler = handler

    def set_state_handler(self, handler: Callable):
        self.state_handler = handler

    #pylint: disable=not-callable
    def call_map_handler(self, *args, **kwargs):
        if self.map_handler:
            self.map_handler(*args, **kwargs)

    def call_chat_handler(self, *args, **kwargs):
        if self.chat_handler:
            self.chat_handler(*args, **kwargs)

    def call_state_handler(self, *args, **kwargs):
        if self.state_handler:
            self.state_handler(*args, **kwargs)

    #pylint: enable=not-callable
    def _receive_data(self):
        """starts infinite socket receiver loop"""
        while True:
            data = self.socket.recv(4096)
            self.packets.append(data)
            self.data_buf += data

    def _process_data(self):
        while True:
            packet_length = 0
            if not packet_length:
                for i in self.data_buf:
                    if 0x80 & i == 0:
                        packet_length = read_VarInt(self.data_buf)
                        break
                else:
                    continue

            if len(self.data_buf) - packet_length[1] < packet_length[0]:
                continue

            # packet is in buffer and ready to be read
            packet_raw = self.data_buf[:packet_length[0] + packet_length[1]]
            self.packets_1.append(packet_raw)
            packet_raw_pointer = packet_length[1]

            if self.compression_enabled:
                packet_compressed_size, packet_raw_pointer = read_VarInt(
                    packet_raw, packet_raw_pointer)
                if packet_compressed_size:
                    packet = zlib.decompress(packet_raw[packet_raw_pointer:])
                else:
                    packet = packet_raw[packet_raw_pointer:]
            else:
                packet = packet_raw[packet_raw_pointer:]

            packet_id, packet_pointer = read_VarInt(packet)
            self.packets_2.append([hex(packet_id), packet])

            if self.state == STATE_LOGIN:
                if packet_id == 0x00:
                    reason, packet_pointer = read_Chat(packet, packet_pointer)
                    self.state = STATE_DISCONNECT
                    self.call_state_handler({
                        "state": self.state,
                        "msg": json.loads(reason)
                    })
                elif packet_id == 0x02:
                    self.state = STATE_PLAY
                    self.info["uuid"], packet_pointer = read_String(
                        packet, packet_pointer)
                    self.info["username"], packet_pointer = read_String(
                        packet, packet_pointer)
                    self.call_state_handler({"state": self.state})
                elif packet_id == 0x03:
                    self.compression_enabled = True

            elif self.state == STATE_PLAY:
                if packet_id == 0x01:
                    self.info["entity_id"], packet_pointer = read_Int(
                        packet, packet_pointer)
                    self.info["gamemode"], packet_pointer = read_UByte(
                        packet, packet_pointer)
                    self.info["dimension"], packet_pointer = read_Byte(
                        packet, packet_pointer)
                    self.info["difficulty"], packet_pointer = read_UByte(
                        packet, packet_pointer)
                    self.info["max_players"], packet_pointer = read_UByte(
                        packet, packet_pointer)
                    self.info["level_type"], packet_pointer = read_String(
                        packet, packet_pointer)
                    self.info[
                        "reduced_debug_info"], packet_pointer = read_Boolean(
                            packet, packet_pointer)
                elif packet_id == 0x3f:
                    # Plugin Message
                    self.handle_plugin_message(packet[packet_pointer:])
                elif packet_id == 0x41:
                    # Server Difficulty
                    self.info["difficulty"], packet_pointer = read_UByte(
                        packet, packet_pointer)
                elif packet_id == 0x05:
                    # Spawn Position
                    x, y, z, packet_pointer = read_Position(
                        packet, packet_pointer)
                    print(x, y, z)
                elif packet_id == 0x39:
                    # Player abilities
                    self.info["abilites_flag"], packet_pointer = read_Byte(
                        packet, packet_pointer)
                    self.info["flying_speed"], packet_pointer = read_Float(
                        packet, packet_pointer)
                    self.info[
                        "field_of_view_modifier"], packet_pointer = read_Float(
                            packet, packet_pointer)
                elif packet_id == 0x09:
                    # Held item change
                    self.info["held_item"], packet_pointer = read_Byte(
                        packet, packet_pointer)
                elif packet_id == 0x37:
                    # Statistics
                    print("0x37 (Statistics)")
                    count, packet_pointer = read_VarInt(packet, packet_pointer)
                    statistics = {}
                    for i in range(count):
                        name, packet_pointer = read_String(
                            packet, packet_pointer)
                        value, packet_pointer = read_VarInt(
                            packet, packet_pointer)
                        statistics[name] = value
                    print(statistics)
                elif packet_id == 0x02:
                    # Chat Message
                    chat, packet_pointer = read_Chat(packet, packet_pointer)
                    chat_position, packet_pointer = read_Byte(
                        packet, packet_pointer)
                    self.call_chat_handler({
                        "chat": chat,
                        "chat_position": chat_position
                    })
                elif packet_id == 0x38:
                    # Player List Item
                    print("0x38 (Player List Item)")
                    action, packet_pointer = read_VarInt(
                        packet, packet_pointer)
                    number_of_player, packet_pointer = read_VarInt(
                        packet, packet_pointer)
                    player_list = []
                    for i in range(number_of_player):
                        player_UUID, packet_pointer = read_UUID(
                            packet, packet_pointer)
                        if action == ACTION_ADD_PLAYER:
                            player_name, packet_pointer = read_String(
                                packet, packet_pointer)
                            number_of_properties, packet_pointer = read_VarInt(
                                packet, packet_pointer)
                            player_properties = {}
                            for _ in range(number_of_properties):
                                property_name, packet_pointer = read_String(
                                    packet, packet_pointer)
                                property_value, packet_pointer = read_String(
                                    packet, packet_pointer)
                                property_is_signed, packet_pointer = read_Boolean(
                                    packet, packet_pointer)
                                property_signature = ""
                                if property_is_signed:
                                    property_signature, packet_pointer = read_String(
                                        packet, packet_pointer)
                                player_properties[property_name] = [
                                    property_value, property_is_signed,
                                    property_signature
                                ]
                            player_gamemode, packet_pointer = read_VarInt(
                                packet, packet_pointer)
                            player_ping, packet_pointer = read_VarInt(
                                packet, packet_pointer)
                            player_has_display_name, packet_pointer = read_Boolean(
                                packet, packet_pointer)
                            player_display_name = ""
                            if player_has_display_name:
                                player_display_name, packet_pointer = read_Chat(
                                    packet, packet_pointer)
                            player_list.append({
                                "player_uuid":
                                player_UUID,
                                "player_name":
                                player_name,
                                "player_properties":
                                player_properties,
                                "player_gamemode":
                                player_gamemode,
                                "player_ping":
                                player_ping,
                                "player_has_display_name":
                                player_has_display_name,
                                "player_display_name":
                                player_display_name
                            })
                        elif action == ACTION_UPDATE_GAMEMODE:
                            player_gamemode, packet_pointer = read_VarInt(
                                packet, packet_pointer)
                            player_list.append({
                                "player_uuid":
                                player_UUID,
                                "player_gamemode":
                                player_gamemode
                            })
                        elif action == ACTION_UPDATE_LATENCY:
                            player_latency, packet_pointer = read_VarInt(
                                packet, packet_pointer)
                            player_list.append({
                                "player_uuid": player_UUID,
                                "player_latency": player_latency
                            })
                        elif action == ACTION_UPDATE_DISPLAY_NAME:
                            player_has_display_name, packet_pointer = read_Boolean(
                                packet, packet_pointer)
                            player_display_name = ""
                            if player_has_display_name:
                                player_display_name, packet_pointer = read_Chat(
                                    packet, packet_pointer)
                            player_list.append({
                                "player_uuid":
                                player_UUID,
                                "player_has_display_name":
                                player_has_display_name,
                                "player_display_name":
                                player_display_name
                            })
                        elif action == ACTION_REMOVE_PLAYER:
                            player_list.append({
                                "player_uuid": player_UUID,
                            })
                        print("Action:", action, player_list)
                elif packet_id == 0x08:
                    # Player Position And Look
                    # TODO: relative and absolute
                    print("0x08 (Player Position And Look)")
                    player_x, packet_pointer = read_Double(
                        packet, packet_pointer)
                    player_y, packet_pointer = read_Double(
                        packet, packet_pointer)
                    player_z, packet_pointer = read_Double(
                        packet, packet_pointer)
                    player_yaw, packet_pointer = read_Float(
                        packet, packet_pointer)
                    player_pitch, packet_pointer = read_Float(
                        packet, packet_pointer)
                    player_flags, packet_pointer = read_Byte(
                        packet, packet_pointer)
                    print("x\t\t", "y\t\t", "z\t\t", "yaw\t\t", "pitch\t\t",
                          "flags")
                    print(player_x, "\t\t", player_y, "\t\t", player_z, "\t",
                          player_yaw, "\t\t", player_pitch, "\t\t",
                          "0b" + bin(player_flags)[2:].rjust(8, "0"))
                elif packet_id == 0x44:
                    # World Border
                    # TODO: implement
                    print("0x44 (World Border, currently not implemented)")
                elif packet_id == 0x03:
                    # Time Update
                    # TODO: implement
                    if LOG_TIME_UPDATES:
                        print("0x03 (Time Update)")
                        world_age, packet_pointer = read_Long(
                            packet, packet_pointer)
                        time_of_day, packet_pointer = read_Long(
                            packet, packet_pointer)
                        print("world_age:", world_age, "time_of_day:",
                              time_of_day)
                elif packet_id == 0x30:
                    # Window Items
                    print("0x30 (Window Items)")
                    window_id, packet_pointer = read_UByte(
                        packet, packet_pointer)
                    count, packet_pointer = read_Short(packet, packet_pointer)
                    items = []
                    print("count", count)
                    for i in range(count):
                        item_data, packet_pointer = read_Slot(
                            packet, packet_pointer)
                        items.append(item_data)
                    print(window_id, count, items, len(items))
                elif packet_id == 0x40:
                    # Disconnect
                    reason, packet_pointer = read_Chat(packet, packet_pointer)
                    self.state = STATE_DISCONNECT
                    self.call_state_handler({
                        "state": STATE_DISCONNECT,
                        "msg": reason
                    })
                elif packet_id == 0x2f:
                    print("0x2f (Set slot data)")
                    window_id, packet_pointer = read_Byte(
                        packet, packet_pointer)
                    slot, packet_pointer = read_Short(packet, packet_pointer)
                    slot_data, packet_pointer = read_Slot(
                        packet, packet_pointer)
                    print(window_id, slot, slot_data)
                elif packet_id == 0x26:
                    print("0x26 (Map chunk bulk, not implemented)")
                elif packet_id == 0x35:
                    print("0x35 (Update Block Entity)")
                    x, y, z, packet_pointer = read_Position(
                        packet, packet_pointer)
                    action, packet_pointer = read_UByte(packet, packet_pointer)
                    nbt_data, packet_pointer = read_Byte(
                        packet, packet_pointer)
                    if nbt_data != 0:
                        nbt_data = parse_NBT_stream(packet, packet_pointer - 1)
                    print(x, y, z, action, nbt_data)
                elif packet_id == 0x0f:
                    print("0x0f (Spawn Mob, not implemented)")
                elif packet_id == 0x2f:
                    print("0x2f (Set Slot)")
                    window_id, packet_pointer = read_Byte(
                        packet, packet_pointer)
                    slot, packet_pointer = read_Short(packet, packet_pointer)
                    slot_data, packet_pointer = read_Slot(
                        packet, packet_pointer)
                elif packet_id == 0x1c:
                    print("0x1c (Entity Metadata, not implemented)")
                    entity_id, packet_pointer = read_VarInt(
                        packet, packet_pointer)
                elif packet_id == 0x20:
                    print("0x20 (Entity properties, not impelemented)")
                elif packet_id == 0x19:
                    print("0x19 (Resorce Pack Status, not implemented)")
                elif packet_id == 0x0e:
                    print("0x0e (Spawn Object, not implemented)")
                elif packet_id == 0x12:
                    print("0x12 (Entity Velocity, not implemented)")
                elif packet_id == 0x18:
                    print("0x18 (Entity Teleport, not implemeted)")
                elif packet_id == 0x15:
                    print("0x15 (Entity Relative Move, not implemented)")
                elif packet_id == 0x17:
                    print(
                        "0x17 (Entity Look And Relative Move, not implemented)"
                    )
                elif packet_id == 0x1a:
                    print("0x1a (Entity Status, not implemented)")
                elif packet_id == 0x00:
                    print("0x00 (Keep Alive)", packet, packet_raw)
                    keep_alive_id, packet_pointer = read_VarInt(
                        packet, packet_pointer)
                    print(keep_alive_id)
                    self.socket.send(packet_raw)

                elif packet_id == 0x21:
                    print("0x21 (Chunk Data, not implemented)")
                elif packet_id == 0x16:
                    print("0x16 (Entity Look, not implemented)")
                elif packet_id == 0x29:
                    print("0x29 (Sound Effect)")
                    sound_name, packet_pointer = read_String(
                        packet, packet_pointer)
                    effect_position_x, packet_pointer = read_Int(
                        packet, packet_pointer)
                    effect_position_x *= 8
                    effect_position_y, packet_pointer = read_Int(
                        packet, packet_pointer)
                    effect_position_y *= 8
                    effect_position_z, packet_pointer = read_Int(
                        packet, packet_pointer)
                    effect_position_z *= 8
                    volume, packet_pointer = read_Float(packet, packet_pointer)
                    pitch, packet_pointer = read_UByte(packet, packet_pointer)
                    print(sound_name, effect_position_x, effect_position_y,
                          effect_position_z, volume, pitch)
                elif packet_id == 0x28:
                    print("0x28 (Effect)")
                    effect_id, packet_pointer = read_Int(
                        packet, packet_pointer)
                    x, y, z, packet_pointer = read_Position(
                        packet, packet_pointer)
                    data, packet_pointer = read_Int(packet, packet_pointer)
                    disable_relative_volume, packet_pointer = read_Boolean(
                        packet, packet_pointer)
                    print(effect_id, x, y, z, data, disable_relative_volume)
                elif packet_id == 0x13:
                    print("0x13 (Destroy Entities)")
                    count, packet_pointer = read_VarInt(packet, packet_pointer)
                    entity_ids = []
                    for i in range(count):
                        tmp, packet_pointer = read_VarInt(
                            packet, packet_pointer)
                        entity_ids.append(tmp)
                    print(entity_ids)
                elif packet_id == 0x23:
                    print("0x23 (Block Change)")
                    x, y, z, packet_pointer = read_Position(
                        packet, packet_pointer)
                    block_id, packet_pointer = read_VarInt(
                        packet, packet_pointer)
                    print(x, y, z, block_id)
                elif packet_id == 0x0c:
                    print("0x0c (Spawn Player)")
                    entity_id, packet_pointer = read_VarInt(
                        packet, packet_pointer)
                    player_uuid, packet_pointer = read_UUID(
                        packet, packet_pointer)
                    x, packet_pointer = read_Int(packet, packet_pointer)
                    x = (x & 0x1f) * (1 / 32) + ((x & ~(0x1f)) >> 5)
                    y, packet_pointer = read_Int(packet, packet_pointer)
                    y = (y & 0x1f) * (1 / 32) + ((y & ~(0x1f)) >> 5)
                    z, packet_pointer = read_Int(packet, packet_pointer)
                    z = (z & 0x1f) * (1 / 32) + ((z & ~(0x1f)) >> 5)
                    yaw, packet_pointer = read_Angle(packet, packet_pointer)
                    pitch, packet_pointer = read_Angle(packet, packet_pointer)
                    current_item, packet_pointer = read_Short(
                        packet, packet_pointer)
                    metadata, packet_pointer = parse_entity_metadata(
                        packet, packet_pointer)
                    print(entity_id, player_uuid, x, y, z, yaw, pitch,
                          current_item, metadata)
                elif packet_id == 0x04:
                    print("0x04 (Entity Equipment)")
                    entity_id, packet_pointer = read_VarInt(
                        packet, packet_pointer)
                    slot, packet_pointer = read_Short(packet, packet_pointer)
                    item, packet_pointer = read_Slot(packet, packet_pointer)
                    print(entity_id, slot, item)
                elif packet_id == 0x0b:
                    print("0x0b (Animation)")
                    entity_id, packet_pointer = read_VarInt(
                        packet, packet_pointer)
                    animation, packet_pointer = read_UByte(
                        packet, packet_pointer)
                    print(entity_id, animation)
                elif packet_id == 0x42:
                    print("0x42 (Combat Event)")
                    event, packet_pointer = read_VarInt(packet, packet_pointer)
                    duration = 0
                    player_id = 0
                    entity_id = 0
                    message = ""
                    if event == END_COMBAT:
                        duration, packet_pointer = read_VarInt(
                            packet, packet_pointer)
                        entity_id, packet_pointer = read_Int(
                            packet, packet_pointer)
                    if event == ENTITY_DEAD:
                        player_id, packet_pointer = read_VarInt(
                            packet, packet_pointer)
                        entity_id, packet_pointer = read_Int(
                            packet, packet_pointer)
                        message, packet_pointer = read_String(
                            packet, packet_pointer)
                    print(event, duration, player_id, entity_id, message)
                elif packet_id == 0x22:
                    print("0x22 (Multi Block Change, not implemented)")
                elif packet_id == 0x2e:
                    print("0x2e (Close Window, not implemented)")
                elif packet_id == 0x27:
                    print("0x27 (Explosion, not implemented)")
                elif packet_id == 0x2a:
                    print("0x2a (Particle, not implemented)")
                elif packet_id == 0x2b:
                    print("0x2b (Change Game State)")
                    reason, packet_pointer = read_UByte(packet, packet_pointer)
                    value, packet_pointer = read_Float(packet, packet_pointer)
                    print(reason, value)
                elif packet_id == 0x0d:
                    print("0x0d (Collect Item, not implemented)")
                elif packet_id == 0x1b:
                    print("0x1b (Attach Entity, not implemented)")
                elif packet_id == 0x11:
                    print("0x11 (Spawn Experience Orb, not implemented)")
                else:
                    raise RuntimeError("Ran into not implemented packet: " +
                                       hex(packet_id))

            # clear data buffer and go on
            self.data_buf = self.data_buf[packet_length[0] + packet_length[1]:]

    def login_as(self, nickname: str):
        """Logins to minecraft server"""
        handshake_packet = VarInt(0x00) + VarInt(47) + String(
            "localhost") + UShort("25565") + VarInt(2)
        self.send_packet(handshake_packet)
        login_start_packet = VarInt(0x00) + String(nickname)
        self.send_packet(login_start_packet)

        self.receive_data_thread = threading.Thread(target=self._receive_data,
                                                    daemon=True)
        self.receive_data_thread.start()
        self.process_data_thread = threading.Thread(target=self._process_data,
                                                    daemon=True)
        self.process_data_thread.start()

    def join_threads(self):
        """Joins threads in order to keep connection when main thread finishes"""
        self.receive_data_thread.join()
        self.process_data_thread.join()

    def check_status(self, nickname: str):
        raise NotImplementedError()

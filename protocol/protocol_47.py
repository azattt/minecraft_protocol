import json
import socket
import threading
import time
from typing import Callable
import zlib
from protocol.protocol_types import (
    String, UShort, VarInt, parse_NBT_stream, parse_entity_metadata,
    read_Angle, read_Boolean, read_Byte, read_Chat, read_Double, read_Float,
    read_Int, read_Long, read_Position, read_Short, read_Slot, read_String,
    read_UByte, read_UShort, read_UUID, read_VarInt)
from protocol.constants import *

test = []


def read_Chunk(packet: bytes, packet_pointer: int, bit_mask: int,
               continuous: bool, sky_light: bool) -> tuple[list, int]:
    not_empty_chunks_count = bit_mask.bit_count()
    chunk_column_blocks: list[dict] = [None] * 4096 * not_empty_chunks_count
    for i in range(4096 * not_empty_chunks_count):
        short_int = ((packet[packet_pointer + i * 2]) |
                     (packet[packet_pointer + i * 2 + 1] << 8))

        chunk_column_blocks[i] = {
            "block_id": short_int >> 4,
            "block_meta": short_int & 0xF
        }

    packet_pointer += 8192 * not_empty_chunks_count

    for i in range(2048 * not_empty_chunks_count):
        chunk_column_blocks[i *
                            2]["block_light"] = packet[packet_pointer + i] & 15
        chunk_column_blocks[i * 2 +
                            1]["block_light"] = packet[packet_pointer + i] >> 4
    packet_pointer += 2048 * not_empty_chunks_count

    if sky_light:
        for i in range(2048 * not_empty_chunks_count):
            chunk_column_blocks[i * 2]["sky_light"] = packet[packet_pointer +
                                                             i] & 15
            chunk_column_blocks[i * 2 +
                                1]["sky_light"] = packet[packet_pointer +
                                                         i] >> 4
        packet_pointer += 2048 * not_empty_chunks_count

    chunk_biome = None
    if continuous:
        chunk_biome = [0] * 256
        for j in range(256):
            chunk_biome[j] = packet[packet_pointer + j]
        packet_pointer += 256

    return ({
        "blocks": chunk_column_blocks,
        "biome": chunk_biome
    }, packet_pointer)


class ProtocolClient:
    """Minecraft Protocol Client class"""

    def __init__(self) -> None:
        self.socket: socket.socket = None
        self.socket_lock = threading.Lock()
        self.data_buf = b""
        self.packets = []
        self.packets_1 = []
        self.packets_2 = []
        self.compression_enabled = False
        self.state = STATE_LOGIN
        self.info = {}
        self.receive_data_thread: threading.Thread = None
        self.receive_data_thread_alive = False
        self.process_data_thread: threading.Thread = None
        self.process_data_thread_alive = False
        self.connected = False

        self.map_handler: Callable = None
        self.chat_handler: Callable = None
        self.state_handler: Callable = None

        self.chunk_data = {}

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
        if self.socket:
            self.socket.close()

    def exit(self):
        if self.process_data_thread:
            self.process_data_thread_alive = False
            self.process_data_thread.join()
        if self.receive_data_thread:
            self.receive_data_thread_alive = False
            self.process_data_thread.join()
        self.close_connection()

    def send_packet(self,
                    packet_id: int,
                    packet_data: bytes,
                    compress: bool = True):
        """send packet. blocking"""
        if not self.is_connected():
            raise RuntimeError("Not connected")
        with self.socket_lock:
            uncompressed = VarInt(packet_id) + packet_data
            if self.compression_enabled:
                if compress:
                    compressed = zlib.compress(uncompressed)
                    uncompressed_length = VarInt(len(uncompressed))
                    packet = uncompressed_length + compressed
                    self.socket.sendall(
                        VarInt(len(packet) + len(uncompressed_length)) +
                        packet)
                else:
                    uncompressed_length = VarInt(0)
                    packet = uncompressed_length + uncompressed
                    self.socket.sendall(VarInt(len(packet)) + packet)
                print(VarInt(len(packet)) + packet)
            else:
                self.socket.sendall(VarInt(len(uncompressed)) + uncompressed)
                print(VarInt(len(uncompressed)) + uncompressed)

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
        while self.receive_data_thread_alive:
            data = self.socket.recv(4096)
            self.packets.append(data)
            self.data_buf += data

    def _process_data(self):
        while self.process_data_thread_alive:
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
                if packet_id == 0x00:
                    # keep_alive_id, packet_pointer = read_VarInt(
                    #     packet, packet_pointer)
                    with self.socket_lock:
                        self.socket.send(packet_raw)

                elif packet_id == 0x01:
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
                elif packet_id == 0x02:
                    # Chat Message
                    chat, packet_pointer = read_Chat(packet, packet_pointer)
                    chat_position, packet_pointer = read_Byte(
                        packet, packet_pointer)
                    self.call_chat_handler({
                        "chat": chat,
                        "chat_position": chat_position
                    })
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
                    count, packet_pointer = read_VarInt(packet, packet_pointer)
                    statistics = {}
                    for i in range(count):
                        name, packet_pointer = read_String(
                            packet, packet_pointer)
                        value, packet_pointer = read_VarInt(
                            packet, packet_pointer)
                        statistics[name] = value
                elif packet_id == 0x38:
                    # Player List Item
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
                elif packet_id == 0x08:
                    # Player Position And Look
                    # TODO: relative and absolute
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
                elif packet_id == 0x44:
                    # World Border
                    # TODO: implement
                    pass
                elif packet_id == 0x03:
                    # Time Update
                    # TODO: implement
                    world_age, packet_pointer = read_Long(
                        packet, packet_pointer)
                    time_of_day, packet_pointer = read_Long(
                        packet, packet_pointer)
                elif packet_id == 0x30:
                    # Window Items
                    window_id, packet_pointer = read_UByte(
                        packet, packet_pointer)
                    count, packet_pointer = read_Short(packet, packet_pointer)
                    items = []
                    for i in range(count):
                        item_data, packet_pointer = read_Slot(
                            packet, packet_pointer)
                        items.append(item_data)
                elif packet_id == 0x40:
                    # Disconnect
                    reason, packet_pointer = read_Chat(packet, packet_pointer)
                    self.state = STATE_DISCONNECT
                    self.call_state_handler({
                        "state": STATE_DISCONNECT,
                        "msg": reason
                    })
                elif packet_id == 0x2f:
                    window_id, packet_pointer = read_Byte(
                        packet, packet_pointer)
                    slot, packet_pointer = read_Short(packet, packet_pointer)
                    slot_data, packet_pointer = read_Slot(
                        packet, packet_pointer)
                elif packet_id == 0x35:
                    x, y, z, packet_pointer = read_Position(
                        packet, packet_pointer)
                    action, packet_pointer = read_UByte(packet, packet_pointer)
                    nbt_data, packet_pointer = read_Byte(
                        packet, packet_pointer)
                    if nbt_data != 0:
                        nbt_data = parse_NBT_stream(packet, packet_pointer - 1)
                elif packet_id == 0x0f:
                    pass
                elif packet_id == 0x2f:
                    window_id, packet_pointer = read_Byte(
                        packet, packet_pointer)
                    slot, packet_pointer = read_Short(packet, packet_pointer)
                    slot_data, packet_pointer = read_Slot(
                        packet, packet_pointer)
                elif packet_id == 0x1c:
                    entity_id, packet_pointer = read_VarInt(
                        packet, packet_pointer)
                elif packet_id == 0x20:
                    pass
                elif packet_id == 0x19:
                    pass
                elif packet_id == 0x0e:
                    pass
                elif packet_id == 0x12:
                    pass
                elif packet_id == 0x18:
                    pass
                elif packet_id == 0x15:
                    pass
                elif packet_id == 0x17:
                    pass
                elif packet_id == 0x1a:
                    pass
                elif packet_id == 0x21:
                    if self.map_handler:
                        chunk_x, packet_pointer = read_Int(
                            packet, packet_pointer)
                        chunk_z, packet_pointer = read_Int(
                            packet, packet_pointer)
                        ground_up_continuous, packet_pointer = read_Boolean(
                            packet, packet_pointer)
                        primary_bit_mask, packet_pointer = read_UShort(
                            packet, packet_pointer)
                        size, packet_pointer = read_VarInt(
                            packet, packet_pointer)
                        # TODO: we assume that player is in the Overworld hence sky light is sent
                        chunk, packet_pointer = read_Chunk(
                            packet, packet_pointer, primary_bit_mask, True,
                            ground_up_continuous)
                        self.call_map_handler({
                            "type": MAP_CHUNK_DATA,
                            "chunk_x": chunk_x,
                            "chunk_z": chunk_z,
                            "ground_up_continuous": ground_up_continuous,
                            "size": size,
                            "chunk": chunk
                        })

                elif packet_id == 0x22:
                    if self.map_handler:
                        chunk_x, packet_pointer = read_Int(
                            packet, packet_pointer)
                        chunk_z, packet_pointer = read_Int(
                            packet, packet_pointer)
                        record_count, packet_pointer = read_VarInt(
                            packet, packet_pointer)
                        records = []
                        for i in range(record_count):
                            horizontal_position, packet_pointer = read_UByte(
                                packet, packet_pointer)
                            x = horizontal_position & 0xf0
                            z = horizontal_position & 0x0f
                            y, packet_pointer = read_UByte(
                                packet, packet_pointer)
                            block_id, packet_pointer = read_VarInt(
                                packet, packet_pointer)
                            records.append({
                                "position": (x, y, z),
                                "block_id": block_id
                            })
                        self.call_map_handler({
                            "type": MAP_MULTI_BLOCK_CHANGE,
                            "chunk_x": chunk_x,
                            "chunk_z": chunk_z,
                            "records": records
                        })
                elif packet_id == 0x23:
                    if self.map_handler:
                        x, y, z, packet_pointer = read_Position(
                            packet, packet_pointer)
                        block_id, packet_pointer = read_VarInt(
                            packet, packet_pointer)
                        self.call_map_handler({
                            "type": MAP_BLOCK_CHANGE,
                            "location": (x, y, z),
                            "block_id": block_id
                        })
                elif packet_id == 0x24:
                    if self.map_handler:
                        x, y, z, packet_pointer = read_Position(
                            packet, packet_pointer)
                        byte_1, packet_pointer = read_UByte(
                            packet, packet_pointer)
                        byte_2, packet_pointer = read_UByte(
                            packet, packet_pointer)
                        block_type, packet_pointer = read_VarInt(
                            packet, packet_pointer)
                        self.call_map_handler({
                            "type": MAP_BLOCK_ACTION,
                            "location": (x, y, z),
                            "byte_1": byte_1,
                            "byte_2": byte_2,
                            "block_type": block_type
                        })
                elif packet_id == 0x25:
                    if self.map_handler:
                        entity_id, packet_pointer = read_VarInt(
                            packet, packet_pointer)
                        x, y, z, packet_pointer = read_Position(
                            packet, packet_pointer)
                        destroy_stage, packet_pointer = read_Byte(
                            packet, packet_pointer)
                        self.call_map_handler({
                            "type": MAP_BLOCK_BREAK_ANIMATION,
                            "entity_id": entity_id,
                            "location": (x, y, z),
                            "destroy_stage": destroy_stage
                        })
                elif packet_id == 0x26:
                    # bulk
                    if self.map_handler:
                        sky_light_send, packet_pointer = read_Boolean(
                            packet, packet_pointer)
                        chunk_column_count, packet_pointer = read_VarInt(
                            packet, packet_pointer)
                        chunk_meta = []
                        for i in range(chunk_column_count):
                            chunk_x, packet_pointer = read_Int(
                                packet, packet_pointer)
                            chunk_z, packet_pointer = read_Int(
                                packet, packet_pointer)
                            primary_bit_mask, packet_pointer = read_UShort(
                                packet, packet_pointer)
                            chunk_meta.append({
                                "chunk_x":
                                chunk_x,
                                "chunk_z":
                                chunk_z,
                                "primary_bit_mask":
                                primary_bit_mask
                            })
                        chunks = []
                        for meta in chunk_meta:
                            chunk, packet_pointer = read_Chunk(
                                packet, packet_pointer,
                                meta["primary_bit_mask"], sky_light_send, True)
                            chunks.append({
                                "chunk_x": meta["chunk_x"],
                                "chunk_z": meta["chunk_z"],
                                "sky_light_send": sky_light_send,
                                "chunk": chunk
                            })
                        self.call_map_handler({
                            "type": MAP_CHUNK_BULK,
                            "chunks": chunks
                        })

                elif packet_id == 0x16:
                    pass
                elif packet_id == 0x29:
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
                elif packet_id == 0x28:
                    pass
                    effect_id, packet_pointer = read_Int(
                        packet, packet_pointer)
                    x, y, z, packet_pointer = read_Position(
                        packet, packet_pointer)
                    data, packet_pointer = read_Int(packet, packet_pointer)
                    disable_relative_volume, packet_pointer = read_Boolean(
                        packet, packet_pointer)
                elif packet_id == 0x13:
                    count, packet_pointer = read_VarInt(packet, packet_pointer)
                    entity_ids = []
                    for i in range(count):
                        tmp, packet_pointer = read_VarInt(
                            packet, packet_pointer)
                        entity_ids.append(tmp)
                elif packet_id == 0x0c:
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
                elif packet_id == 0x04:
                    entity_id, packet_pointer = read_VarInt(
                        packet, packet_pointer)
                    slot, packet_pointer = read_Short(packet, packet_pointer)
                    item, packet_pointer = read_Slot(packet, packet_pointer)
                elif packet_id == 0x0b:
                    entity_id, packet_pointer = read_VarInt(
                        packet, packet_pointer)
                    animation, packet_pointer = read_UByte(
                        packet, packet_pointer)
                elif packet_id == 0x42:
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
                elif packet_id == 0x2e:
                    pass
                elif packet_id == 0x27:
                    pass
                elif packet_id == 0x2a:
                    pass
                elif packet_id == 0x2b:
                    reason, packet_pointer = read_UByte(packet, packet_pointer)
                    value, packet_pointer = read_Float(packet, packet_pointer)
                elif packet_id == 0x0d:
                    pass
                elif packet_id == 0x1b:
                    pass
                elif packet_id == 0x11:
                    pass
                else:
                    raise RuntimeError("Ran into not implemented packet: " +
                                       hex(packet_id))

            # clear data buffer and go on
            self.data_buf = self.data_buf[packet_length[0] + packet_length[1]:]

    def login_as(self, nickname: str):
        """Logins to minecraft server"""
        handshake_packet = VarInt(47) + String("localhost") + UShort(
            "25565") + VarInt(2)
        self.send_packet(0x00, handshake_packet)
        login_start_packet = String(nickname)
        self.send_packet(0x00, login_start_packet)

        self.receive_data_thread_alive = True
        self.receive_data_thread = threading.Thread(target=self._receive_data,
                                                    daemon=True)
        self.receive_data_thread.start()

        self.process_data_thread_alive = True
        self.process_data_thread = threading.Thread(target=self._process_data,
                                                    daemon=True)
        self.process_data_thread.start()

    def join_threads(self):
        """Joins threads in order to keep connection when main thread finishes"""
        self.receive_data_thread.join()
        self.process_data_thread.join()

    def check_status(self, nickname: str):
        raise NotImplementedError()


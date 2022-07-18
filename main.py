import argparse
import socket
import threading
import zlib
import json
from nbt import parse_NBT_stream

from protocol_types import (String, UShort, VarInt, read_Boolean, read_Byte,
                            read_Chat, read_Double, read_Float, read_Int,
                            read_Long, read_Position, read_Short, read_String,
                            read_UByte, read_UUID, read_VarInt)

LOG_TIME_UPDATES = 0

STATE_LOGIN = 0
STATE_PLAY = 1

data_buf = b""
g_state = STATE_LOGIN
compression_enabled = False
packets = []
packets_1 = []
packets_2 = []

info = {}


def handle_plugin_message(data: bytes) -> int:
    """ Handling minecraft plugin messages"""
    channel, pointer = read_String(data)
    print(channel)
    if channel == "MC|Brand":
        info["host_brand"], _ = read_String(data, pointer)
    return 0


#pylint: disable=missing-function-docstring, global-statement
def process_data():
    global data_buf, g_state, compression_enabled
    while True:
        packet_length = 0
        if not packet_length:
            for i in data_buf:
                if 0x80 & i == 0:
                    packet_length = read_VarInt(data_buf)
                    break
            else:
                continue

        if len(data_buf) - packet_length[1] < packet_length[0]:
            continue

        # packet is in buffer and ready to be read
        packet_raw = data_buf[:packet_length[0] + packet_length[1]]
        packets_1.append(packet_raw)
        packet_raw_pointer = packet_length[1]

        if compression_enabled:
            packet_compressed_size, packet_raw_pointer = read_VarInt(
                packet_raw, packet_raw_pointer)
            if packet_compressed_size:
                packet = zlib.decompress(packet_raw[packet_raw_pointer:])
            else:
                packet = packet_raw[packet_raw_pointer:]
        else:
            packet = packet_raw[packet_raw_pointer:]

        packet_id, packet_pointer = read_VarInt(packet)
        packets_2.append([hex(packet_id), packet])

        if g_state == STATE_LOGIN:
            if packet_id == 0x00:
                print("0x00 (Login disconnect)")
                reason, packet_pointer = read_Chat(packet, packet_pointer)
                print(json.loads(reason))
            elif packet_id == 0x02:
                g_state = STATE_PLAY
                info["uuid"], packet_pointer = read_String(
                    packet, packet_pointer)
                info["username"], packet_pointer = read_String(
                    packet, packet_pointer)
            elif packet_id == 0x03:
                compression_enabled = True

        elif g_state == STATE_PLAY:
            if packet_id == 0x01:
                info["entity_id"], packet_pointer = read_Int(
                    packet, packet_pointer)
                info["gamemode"], packet_pointer = read_UByte(
                    packet, packet_pointer)
                info["dimension"], packet_pointer = read_Byte(
                    packet, packet_pointer)
                info["difficulty"], packet_pointer = read_UByte(
                    packet, packet_pointer)
                info["max_players"], packet_pointer = read_UByte(
                    packet, packet_pointer)
                info["level_type"], packet_pointer = read_String(
                    packet, packet_pointer)
                info["reduced_debug_info"], packet_pointer = read_Boolean(
                    packet, packet_pointer)
            elif packet_id == 0x3f:
                # Plugin Message
                handle_plugin_message(packet[packet_pointer:])
            elif packet_id == 0x41:
                # Server Difficulty
                info["difficulty"], packet_pointer = read_UByte(
                    packet, packet_pointer)
            elif packet_id == 0x05:
                # Spawn Position
                x, y, z, packet_pointer = read_Position(packet, packet_pointer)
                print(x, y, z)
            elif packet_id == 0x39:
                # Player abilities
                info["abilites_flag"], packet_pointer = read_Byte(
                    packet, packet_pointer)
                info["flying_speed"], packet_pointer = read_Float(
                    packet, packet_pointer)
                info["field_of_view_modifier"], packet_pointer = read_Float(
                    packet, packet_pointer)
            elif packet_id == 0x09:
                # Held item change
                info["held_item"], packet_pointer = read_Byte(
                    packet, packet_pointer)
            elif packet_id == 0x37:
                # Statistics
                print("0x37 (Statistics)")
                count, packet_pointer = read_VarInt(packet, packet_pointer)
                statistics = {}
                for i in range(count):
                    name, packet_pointer = read_String(packet, packet_pointer)
                    value, packet_pointer = read_VarInt(packet, packet_pointer)
                    statistics[name] = value
                print(statistics)
            elif packet_id == 0x02:
                # Chat Message
                chat, packet_pointer = read_Chat(packet, packet_pointer)
                chat_position, packet_pointer = read_Byte(
                    packet, packet_pointer)
                print("0x02 (chat)", chat, chat_position)
            elif packet_id == 0x38:
                # Player List Item
                print("0x38 (Player List Item)")
                action, packet_pointer = read_VarInt(packet, packet_pointer)
                number_of_player, packet_pointer = read_VarInt(
                    packet, packet_pointer)
                player_list = []
                for i in range(number_of_player):
                    player_UUID, packet_pointer = read_UUID(
                        packet, packet_pointer)
                    ACTION_ADD_PLAYER = 0
                    ACTION_UPDATE_GAMEMODE = 1
                    ACTION_UPDATE_LATENCY = 2
                    ACTION_UPDATE_DISPLAY_NAME = 3
                    ACTION_REMOVE_PLAYER = 4
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
                            "player_uuid": player_UUID,
                            "player_gamemode": player_gamemode
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
                player_x, packet_pointer = read_Double(packet, packet_pointer)
                player_y, packet_pointer = read_Double(packet, packet_pointer)
                player_z, packet_pointer = read_Double(packet, packet_pointer)
                player_yaw, packet_pointer = read_Float(packet, packet_pointer)
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
                    print("world_age:", world_age, "time_of_day:", time_of_day)
            elif packet_id == 0x30:
                # Window Items
                print("0x30 (Window Items)")
                window_id, packet_pointer = read_UByte(packet, packet_pointer)
                count, packet_pointer = read_Short(packet, packet_pointer)
                items = []
                print("count", count)
                for i in range(count):
                    item_id, packet_pointer = read_Short(
                        packet, packet_pointer)
                    if item_id == -1:
                        items.append([-1])
                    else:
                        items.append([item_id])
                        item_count, packet_pointer = read_Byte(
                            packet, packet_pointer)
                        item_damage, packet_pointer = read_Short(
                            packet, packet_pointer)
                        nbt_byte, packet_pointer = read_Byte(
                            packet, packet_pointer)
                        if nbt_byte:
                            item_nbt, packet_pointer = parse_NBT_stream(
                                packet, packet_pointer - 1)
                            print(item_nbt)
                print(window_id, count, items, len(items))
            elif packet_id == 0x40:
                # Disconnect
                print("0x40 (Disconnect)")
                reason, packet_pointer = read_Chat(packet, packet_pointer)
                print(reason)
            else:
                raise RuntimeError("Ran into not implemented packet: " +
                                   hex(packet_id))

        print("clear")
        # clear data buffer and go on
        data_buf = data_buf[packet_length[0] + packet_length[1]:]


parser = argparse.ArgumentParser()
parser.add_argument("--nickname", help="client's nickname")
args = parser.parse_args()

s = socket.socket()
s.connect(("localhost", 25565))
data = VarInt(0x00) + VarInt(47) + String("localhost") + UShort(
    "25565") + VarInt(2)
packet = VarInt(len(data)) + data
s.send(packet)
if args.nickname:
    data = VarInt(0x00) + String(args.nickname)
else:
    data = VarInt(0x00) + String("Herobrine")

packet = VarInt(len(data)) + data
s.send(packet)

process_data_thread = threading.Thread(target=process_data, daemon=True)
process_data_thread.start()

while True:
    if not process_data_thread.is_alive():
        exit()
    data = s.recv(4096)
    packets.append(data)
    data_buf += data

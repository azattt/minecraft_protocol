"""
Internal stuff for convenient use
"""
import struct
import uuid
from protocol.protocol_tools import (logical_rshift32, logical_rshift64,
                                     signed_to_int, signed32bit_to_int,
                                     signed64bit_to_int)

TAG_END = 0
TAG_BYTE = 1
TAG_SHORT = 2
TAG_INT = 3
TAG_LONG = 4
TAG_FLOAT = 5
TAG_DOUBLE = 6
TAG_BYTE_ARRAY = 7
TAG_STRING = 8
TAG_LIST = 9
TAG_COMPOUND = 10
TAG_INT_ARRAY = 11
TAG_LONG_ARRAY = 12


def parse_NBT_stream(data: bytes, pointer: int = 0) -> tuple[dict, int]:
    """Parses NBT bytes stream. Returns parsed NBT in dict and length of NBT in bytes"""

    def parse_tag(data0: bytes,
                  pointer0: int,
                  force_tag_type: int = 0,
                  have_name: bool = True) -> tuple[dict, int]:
        if not force_tag_type:
            tag_type = data0[pointer0]
            if tag_type == TAG_END or not have_name:
                pointer0 += 1
                name = ""
            else:
                name_length = int.from_bytes(data0[pointer0 + 1:pointer0 + 3],
                                             "big")
                name = data0[pointer0 + 3:pointer0 + 3 + name_length]
                pointer0 += name_length + 3
        else:
            tag_type = force_tag_type
            if tag_type == TAG_END or not have_name:
                name = ""
            else:
                name_length = int.from_bytes(data0[pointer0:pointer0 + 2],
                                             "big")
                name = data0[pointer0 + 2:pointer0 + 2 + name_length]
                pointer0 += name_length + 2
        if tag_type == TAG_END:
            children = []
        elif tag_type == TAG_BYTE:
            children = [(data0[pointer0:pointer0 + 1] ^ 0x80) - 0x80]
            pointer0 += 1
        elif tag_type == TAG_SHORT:
            children = [
                int.from_bytes(data0[pointer0:pointer0 + 2],
                               "big",
                               signed=True)
            ]
            pointer0 += 2
        elif tag_type == TAG_INT:
            children = [
                int.from_bytes(data0[pointer0:pointer0 + 4],
                               "big",
                               signed=True)
            ]
            pointer0 += 4
        elif tag_type == TAG_LONG:
            children = [
                int.from_bytes(data0[pointer0:pointer0 + 8],
                               "big",
                               signed=True)
            ]
            pointer0 += 8
        elif tag_type == TAG_FLOAT:
            children = [struct.unpack(">f", data0[pointer0:pointer0 + 4])]
            pointer0 += 4
        elif tag_type == TAG_DOUBLE:
            children = [struct.unpack(">d", data0[pointer0:pointer0 + 8])]
            pointer0 += 8
        elif tag_type == TAG_BYTE_ARRAY:
            array_size = int.from_bytes(data0[pointer0:pointer0 + 4], "big")
            pointer0 += 4
            children = [(byte[0] ^ 0x80) - 0x80
                        for byte in data0[pointer0:pointer0 + array_size]]
            pointer0 += array_size
        elif tag_type == TAG_STRING:
            string_length = int.from_bytes(data0[pointer0:pointer0 + 2], "big")
            pointer0 += 2
            children = [
                data0[pointer0:pointer0 + string_length].decode("utf8")
            ]
            pointer0 += string_length
        elif tag_type == TAG_LIST:
            list_tag_id = (data0[pointer0] ^ 0x80) - 0x80
            list_size = int.from_bytes(data0[pointer0 + 1:pointer0 + 5],
                                       "big",
                                       signed=True)
            pointer0 += 5
            children = []
            for _ in range(list_size):
                parsed, pointer0 = parse_tag(data0,
                                             pointer0,
                                             force_tag_type=list_tag_id,
                                             have_name=False)
                children.append(parsed)
        elif tag_type == TAG_COMPOUND:
            children = []
            while True:
                parsed, pointer0 = parse_tag(data0, pointer0)
                if parsed["type"] == TAG_END:
                    break
                children.append(parsed)

        return ({
            "type": tag_type,
            "name": name,
            "children": children
        }, pointer0)

    if data[pointer] != TAG_COMPOUND:
        raise RuntimeError(
            "Could not pass NBT: given NBT doesn't start with Compound tag")

    return parse_tag(data, pointer)


def parse_entity_metadata(data: bytes, pointer: int) -> tuple[dict, int]:
    parsed = []
    while True:
        index, pointer = read_UByte(data, pointer)
        if index == 0x7f:
            break
        e_type = (index & 0xe0) >> 5
        e_key = (index & 0x1f)
        if e_type == 0:
            value, pointer = read_Byte(data, pointer)
        elif e_type == 1:
            value, pointer = read_Short(data, pointer)
        elif e_type == 2:
            value, pointer = read_Int(data, pointer)
        elif e_type == 3:
            value, pointer = read_Float(data, pointer)
        elif e_type == 4:
            value, pointer = read_String(data, pointer)
        elif e_type == 5:
            value, pointer = read_Slot(data, pointer)
        elif e_type == 6:
            x, pointer = read_Int(data, pointer)
            y, pointer = read_Int(data, pointer)
            z, pointer = read_Int(data, pointer)
            value = (x, y, z)
        elif e_type == 7:
            x, pointer = read_Float(data, pointer)
            y, pointer = read_Float(data, pointer)
            z, pointer = read_Float(data, pointer)
            value = (x, y, z)
        parsed.append({"type": e_type, "key": e_key, "value": value})
    return (parsed, pointer)


# def parse_entity_metadata(data: bytes, pointer: int) -> tuple[dict, int]:
#     parsed = []
#     while True:
#         index, pointer = read_UByte(data, pointer)
#         if index == 0xff:
#             break
#         index_type, pointer = read_VarInt(data, pointer)
#         value = 0
#         if index_type == 0:
#             value, pointer = read_Byte(data, pointer)
#         elif index_type == 1:
#             value, pointer = read_VarInt(data, pointer)
#         elif index_type == 2:
#             value, pointer = read_Float(data, pointer)
#         elif index_type == 3:
#             value, pointer = read_String(data, pointer)
#         elif index_type == 4:
#             value, pointer = read_Chat(data, pointer)
#         elif index_type == 5:
#             optchat, pointer = read_Boolean(data, pointer)
#             if optchat:
#                 value, pointer = read_Chat(data, pointer)
#         elif index_type == 6:
#             value, pointer = read_Slot(data, pointer)
#         elif index_type == 7:
#             value, pointer = read_Boolean(data, pointer)
#         elif index_type == 8:
#             value, pointer = read_Angle(data, pointer)
#         elif index_type == 9:
#             x, y, z, pointer = read_Position(data, pointer)
#             value = (x, y, z)
#         elif index_type == 10:
#             optpos, pointer = read_Boolean(data, pointer)
#             if optpos:
#                 x, y, z, pointer = read_Position(data, pointer)
#                 value = (x, y, z)
#         elif index_type == 11:
#             value, pointer = read_VarInt(data, pointer)
#         elif index_type == 12:
#             optuuid, pointer = read_Boolean(data, pointer)
#             if optuuid:
#                 value, pointer = read_UUID(data, pointer)
#         elif index_type == 13:
#             value, pointer = read_VarInt(data, pointer)
#         elif index_type == 14:
#             value, pointer = parse_NBT_stream(data, pointer)
#         elif index_type == 15:
#             value, pointer = read_Particle(data, pointer)
#         elif index_type == 16:
#             value, pointer = read_VarInt(data, pointer)
#         elif index_type == 17:
#             value, pointer = read_VarInt(data, pointer)
#             value -= 1
#         elif index_type == 18:
#             value, pointer = read_VarInt(data, pointer)
#         elif index_type == 19:
#             value, pointer = read_VarInt(data, pointer)
#         elif index_type == 20:
#             value, pointer = read_VarInt(data, pointer)
#         elif index_type == 21:
#             value, pointer = read_VarInt(data, pointer)
#     parsed.append({"index": index, "type": index_type, "value": value})
#     return (parsed, pointer)


def Boolean(value: bool) -> bytes:
    """Minecraft's Boolean type"""
    if value:
        return b'\x01'
    return b'\x00'


def Byte(value: int) -> bytes:
    """Minecraft's Byte type"""
    return int(value).to_bytes(1, 'big', signed=True)


def UByte(value: int) -> bytes:
    """Minecraft's UByte type"""
    return int(value).to_bytes(1, 'big', signed=False)


def Short(value: int) -> bytes:
    """Minecraft's Short type"""
    return int(value).to_bytes(2, 'big', signed=True)


def UShort(value: int) -> bytes:
    """Minecraft's UShort type"""
    return int(value).to_bytes(2, 'big', signed=False)


def Int(value: int) -> bytes:
    """Minecraft's Int type"""
    return int(value).to_bytes(4, 'big', signed=True)


def Long(value: int) -> bytes:
    """Minecraft's Long type"""
    return int(value).to_bytes(8, 'big', signed=True)


def Float(value: float) -> bytes:
    """Minecraft's Float type"""
    return struct.pack(">f", value)


def Double(value: float) -> bytes:
    """Minecraft's Double type"""
    return struct.pack(">d", value)


def VarInt(value: int) -> bytes:
    """Minecraft's VarInt type"""
    buf = b''
    while True:
        towrite = value & 0x7f
        value = logical_rshift32(value, 7)
        if value:
            buf += bytes((towrite | 0x80, ))
        else:
            buf += bytes((towrite, ))
            break
    return buf


def VarLong(value: int) -> bytes:
    """Minecraft's VarLong type"""
    buf = b''
    while True:
        towrite = value & 0x7F
        value = logical_rshift64(value, 7)
        if value:
            buf += bytes((towrite | 0x80, ))
        else:
            buf += bytes((towrite, ))
            break
    return buf


def String(string: str) -> bytes:
    """Minecraft's String type"""
    return VarInt(len(string)) + bytes(string, "utf8")


def Chat(string: str) -> bytes:
    """Minecraft's Chat type"""
    return VarInt(len(string)) + bytes(string, "utf8")


def Identifier(string: str) -> bytes:
    """Minecraft's Identifier type"""
    return VarInt(len(string)) + bytes(string, "utf8")


def UUID(my_uuid: uuid.UUID) -> bytes:
    """Minecraft's UUID type"""
    raise NotImplementedError()


def Position(x: int, y: int, z: int) -> bytes:
    """Minecraft's Position type"""
    return int(((x & 0x3FFFFFF) << 38) | ((y & 0xFFF) << 26)
               | (z & 0x3FFFFFF)).to_bytes(8, "big")


def read_Boolean(value: bytes, pointer: int = 0) -> tuple[bool, int]:
    """
    returns bool and pointer.
    """
    return (bool(value[pointer]), pointer + 1)


def read_Byte(value: bytes, pointer: int = 0) -> tuple[int, int]:
    """
    returns int(-128 - 127) and pointer.
    """
    return ((value[pointer] ^ 0x80) - 0x80, pointer + 1)


def read_UByte(value: bytes, pointer: int = 0) -> tuple[int, int]:
    """
    returns int(0 - 255) and pointer
    """
    return (value[pointer], pointer + 1)


def read_Short(value: bytes, pointer: int = 0) -> tuple[int, int]:
    """
    returns int(-32768 - 32767) and pointer
    """
    return (int.from_bytes(value[pointer:pointer + 2], "big",
                           signed=True), pointer + 2)


def read_UShort(value: bytes, pointer: int = 0) -> tuple[int, int]:
    """
    returns int(0 - 65535) and pointer
    """
    return (int.from_bytes(value[pointer:pointer + 2], "big"), pointer + 2)


def read_Int(value: bytes, pointer: int = 0) -> tuple[int, int]:
    """
    returns 32 bit signed int and pointer.
    """
    return (int.from_bytes(value[pointer:pointer + 4], "big",
                           signed=True), pointer + 4)


def read_Long(value: bytes, pointer: int = 0) -> tuple[int, int]:
    """
    returns 64 bit signed int and pointer.
    """
    return (int.from_bytes(value[pointer:pointer + 8], "big",
                           signed=True), pointer + 8)


def read_Float(value: bytes, pointer: int = 0) -> tuple[float, int]:
    """
    returns single-precision float and pointer.
    """
    return (struct.unpack(">f", value[pointer:pointer + 4])[0], pointer + 4)


def read_Double(value: bytes, pointer: int = 0) -> tuple[float, int]:
    """
    returns double-precision float and pointer.
    """
    return (struct.unpack(">d", value[pointer:pointer + 8])[0], pointer + 8)


def read_VarInt(value: bytes, pointer: int = 0) -> tuple[int, int]:
    """
    returns integer and pointer.
    """
    buf = 0
    n = 0
    for n, i in enumerate(value[pointer:]):
        buf |= ((i & 0x7F) << (7 * n))
        if not i & 0x80:
            break

    return (signed32bit_to_int(buf), pointer + n + 1)


def read_VarLong(value: bytes, pointer: int = 0) -> tuple[int, int]:
    """
    returns integer and pointer.
    """
    buf = 0
    n = 0
    for n, i in enumerate(value[pointer:]):
        buf |= ((i & 0x7F) << (7 * n))
        if not i & 0x80:
            break

    return (signed64bit_to_int(buf), pointer + n + 1)


def read_UUID(value: bytes, pointer: int = 0) -> tuple[uuid.UUID, int]:
    """
    returns uuid and pointer.
    """
    tmp = int.from_bytes(value[pointer:pointer + 16], "big")

    return (uuid.UUID(int=tmp), pointer + 16)


def read_String(value: bytes, pointer: int = 0) -> tuple[str, int]:
    """
    returns string and pointer.
    """
    length, pointer = read_VarInt(value, pointer)
    return (value[pointer:pointer + length].decode("utf8",
                                                   "big"), pointer + length)


def read_Chat(value: bytes, pointer: int = 0) -> tuple[str, int]:
    """
    returns JSON string of chat and pointer.
    """
    length, pointer = read_VarInt(value, pointer)
    return (value[pointer:pointer + length].decode("utf8",
                                                   "big"), pointer + length)


def read_Position(value: bytes, pointer: int = 0) -> tuple[int, int, int, int]:
    """
    returns tuple of (x, y, z) coordinates and a pointer
    """
    data, pointer = read_Long(value, pointer)
    x = signed_to_int(logical_rshift64(data, 38), 26)
    y = signed_to_int(logical_rshift64(data, 26) & 0xFFF, 12)
    z = signed_to_int(data & 0x3FFFFFF, 26)
    return (x, y, z, pointer)


def read_Slot(value: bytes, pointer: int = 0) -> tuple[dict, int]:
    """
    returns dict of slot data and a pointer
    """
    item_id, pointer = read_Short(value, pointer)
    item_count = 0
    item_damage = 0
    item_nbt = {}
    if item_id != -1:
        item_count, pointer = read_Byte(value, pointer)
        item_damage, pointer = read_Short(value, pointer)
        nbt_byte, pointer = read_Byte(value, pointer)
        if nbt_byte:
            item_nbt, pointer = parse_NBT_stream(value, pointer - 1)
    return ({
        "item_id": item_id,
        "item_count": item_count,
        "item_damage": item_damage,
        "item_nbt": item_nbt
    }, pointer)


def read_Angle(value: bytes, pointer: int = 0) -> tuple[int, int]:
    """
    returns a rotation angle in steps of 1/256 of a full turn and a pointer
    """
    return read_UByte(value, pointer)


def read_Particle(value: bytes, pointer: int = 0) -> tuple[dict, int]:
    """
    returns dict with particle data and a pointer
    """
    data = {}
    particle_id, pointer = read_VarInt(value, pointer)
    data["particle_id"] = particle_id
    if particle_id in [2, 3]:
        data["block_state"], pointer = read_VarInt(value, pointer)
    elif particle_id == 14:
        data["red"], pointer = read_Float(value, pointer)
        data["green"], pointer = read_Float(value, pointer)
        data["blue"], pointer = read_Float(value, pointer)
        data["scale"], pointer = read_Float(value, pointer)
    elif particle_id == 15:
        data["from_red"], pointer = read_Float(value, pointer)
        data["from_green"], pointer = read_Float(value, pointer)
        data["from_blue"], pointer = read_Float(value, pointer)
        data["scale"], pointer = read_Float(value, pointer)
        data["to_red"], pointer = read_Float(value, pointer)
        data["to_green"], pointer = read_Float(value, pointer)
        data["to_blue"], pointer = read_Float(value, pointer)
    elif particle_id == 24:
        data["block_state"], pointer = read_VarInt(value, pointer)
    elif particle_id == 35:
        data["item"], pointer = read_Slot(value, pointer)
    elif particle_id == 36:
        data["position_source_type"], pointer = read_String(value, pointer)
        x, y, z, pointer = read_Position(value, pointer)
        data["block_position"] = (x, y, z)
        data["entity_id"], pointer = read_VarInt(value, pointer)
        data["entity_eye_height"], pointer = read_Float(value, pointer)
        data["ticks"], pointer = read_VarInt(value, pointer)
    return (data, pointer)

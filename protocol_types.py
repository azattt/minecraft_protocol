"""
Internal stuff for convenient use
"""
import struct
import uuid
from protocol_tools import (logical_rshift32, logical_rshift64, signed_to_int,
                            signed32bit_to_int, signed64bit_to_int)


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
    return (value[pointer:length + pointer].decode("utf8",
                                                   "big"), pointer + length)


def read_Chat(value: bytes, pointer: int = 0) -> tuple[str, int]:
    """
    returns JSON string of chat and pointer.
    """
    length, pointer = read_VarInt(value, pointer)
    return (value[pointer:length + pointer].decode("utf8",
                                                   "big"), pointer + length)


def read_Position(value: bytes, pointer: int = 0) -> tuple[int, int, int, int]:
    """
    returns tuple of (x, y, z) coordinates and a pointer
    """
    data, pointer = read_Long(value, pointer)
    x = signed_to_int(logical_rshift64(data, 38), 26)
    y = signed_to_int(logical_rshift64(data, 26) & 0xFFF, 12)
    z = signed_to_int(data & 0x3FFFFFF, 26)
    return (x, y, z, pointer + 64)

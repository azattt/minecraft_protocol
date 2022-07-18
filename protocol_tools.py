def logical_rshift32(val: int, amount: int) -> int:
    """logical 32 bit rshift"""
    return (val % (1 << 32)) >> amount


def logical_rshift64(val: int, amount: int) -> int:
    """logical 64 bit rshift"""
    return (val % (1 << 64)) >> amount


def logical_lshift32(val: int, amount: int) -> int:
    """logical 32 bit lshift"""
    return (val % (1 << 32)) >> amount


def logical_lshift64(val: int, amount: int) -> int:
    """logical 64 bit lshift"""
    return (val % (1 << 64)) >> amount


def bin32_2s_comp(val: int) -> str:
    """get string representation of 32 bit int in it's two's complement"""
    tmp = bin(0xffffffff & val)[2:].rjust(32, "0")
    return "0b" + " ".join([tmp[i:i + 8] for i in range(0, len(tmp), 8)])


def bin64_2s_comp(val: int) -> str:
    """get string representation of 64 bit int in it's two's complement"""
    tmp = bin(0xffffffffffffffff & val)[2:].rjust(64, "0")
    return "0b" + " ".join([tmp[i:i + 8] for i in range(0, len(tmp), 8)])


def signed32bit_to_int(value: int) -> int:
    """convert 32 bit two's complement int to python's int """
    return (value & 0xffffffff ^ 0x80000000) - 0x80000000


def signed64bit_to_int(value: int) -> int:
    """convert 64 bit two's complement int to python's int """
    return (value & 0xffffffffffffffff
            ^ 0x8000000000000000) - 0x8000000000000000


def signed_to_int(value: int, bitness: int) -> int:
    """ convert n-bit two's complement int to python's int"""
    return (value & ((1 << bitness) - 1) ^ (1 <<
                                            (bitness - 1))) - (1 <<
                                                               (bitness - 1))


def bytes_to_bits(value: bytes) -> str:
    """get string representation of python bytes in 0b bit style (like bin())"""
    buf = "0b"
    for i in value:
        buf += bin(i)[2:].rjust(8, "0") + " "
    return buf


def reverse_bits(num: int) -> int:
    """reverse bits of int"""
    result = 0
    while num:
        result = (result << 1) + (num & 1)
        num >>= 1
    return result
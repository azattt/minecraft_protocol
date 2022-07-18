TAG_COMPOUND = 10
TAG_LIST = 9


def parse_slot_data(value: bytes, pointer: int) -> tuple[dict, int]:
    """ parse NBT Slot Data like for 0x30 packet"""
    value = value[pointer:]
    ench_size = int.from_bytes(value[11:15], "big")
    for i in range(ench_size):
        pass

    return ({}, pointer)
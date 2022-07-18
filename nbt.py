TAG_COMPOUND = 10
TAG_LIST = 9


def parse_slot_data(value: bytes, pointer: int) -> tuple[dict, int]:
    """ parse NBT Slot Data like for 0x30 packet"""
    value = value[pointer:]
    return ({}, pointer)
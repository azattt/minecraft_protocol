import struct

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

# -*- coding: utf-8 -*-
"""Dependency-free GIF89a writer, compatible with IronPython 2.7.

Fixed RGB 3:3:2 palette with an optional reserved transparent index.
One frame is buffered at a time.
"""
import struct


TRANSPARENT_INDEX = 255


def palette_index(red, green, blue, alpha=255, transparent=False):
    if transparent and alpha < 128:
        return TRANSPARENT_INDEX
    value = ((int(red) >> 5) << 5) | ((int(green) >> 5) << 2) | (int(blue) >> 6)
    if transparent:
        # Reserve 255 for alpha, retaining exact opaque white at 254. The old
        # pale-yellow 254 moves to its closest remaining green neighbour.
        if value == 255:
            return 254
        if value == 254:
            return 250
    return value


def bgra_indices(row, width):
    """Map straight-alpha BGRA bytes; colour similarity never removes pixels."""
    result = bytearray(width)
    for x in range(width):
        offset = x * 4
        result[x] = palette_index(row[offset + 2], row[offset + 1], row[offset],
                                  row[offset + 3], True)
    return result


def _lzw(indices):
    # Reset before the dictionary reaches 512 entries. This intentionally keeps
    # all codes at nine bits, avoiding runtime-specific variable-width packing.
    result = bytearray()
    bits, count = 0, 0

    def codes():
        yield 256
        table = {}
        next_code = 258
        prefix = None
        for item in indices:
            item = int(item)
            if not 0 <= item <= 255:
                raise ValueError("Palette index must be in 0..255")
            if prefix is None:
                prefix = item
                continue
            key = (prefix, item)
            if key in table:
                prefix = table[key]
            else:
                yield prefix
                table[key] = next_code
                next_code += 1
                prefix = item
                if next_code == 500:
                    yield 256
                    table = {}
                    next_code = 258
        if prefix is not None:
            yield prefix
        yield 257

    for code in codes():
        bits |= code << count
        count += 9
        while count >= 8:
            result.append(bits & 255)
            bits >>= 8
            count -= 8
    if count:
        result.append(bits & 255)
    return result


class GifWriter(object):
    def __init__(self, stream, width, height, transparent=False):
        if not 1 <= width <= 65535 or not 1 <= height <= 65535:
            raise ValueError("Invalid GIF dimensions")
        self.stream = stream
        self.width, self.height = width, height
        self.frames = 0
        self.closed = False
        self.transparent = bool(transparent)
        stream.write(b"GIF89a")
        stream.write(struct.pack("<HHBBB", width, height, 247,
                                 TRANSPARENT_INDEX if self.transparent else 0, 0))
        for value in range(256):
            if self.transparent and value == 254:
                stream.write(b"\xff\xff\xff")
                continue
            stream.write(struct.pack("BBB", int(round(((value >> 5) & 7) * 255.0 / 7)),
                                     int(round(((value >> 2) & 7) * 255.0 / 7)),
                                     (value & 3) * 85))
        stream.write(b"\x21\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00")

    def add_frame(self, indices, delay_cs):
        if self.closed:
            raise ValueError("GIF is already closed")
        if len(indices) != self.width * self.height:
            raise ValueError("Frame dimensions do not match")
        if not 1 <= delay_cs <= 65535:
            raise ValueError("Invalid frame delay")
        payload = _lzw(indices)
        # Full frames + restore-to-background disposal prevent old part
        # positions showing through transparent pixels of subsequent frames.
        flags = 9 if self.transparent else 4
        self.stream.write(b"\x21\xf9\x04" + struct.pack("B", flags))
        self.stream.write(struct.pack("<HBB", delay_cs,
                                       TRANSPARENT_INDEX if self.transparent else 0, 0))
        self.stream.write(b"\x2c" + struct.pack("<HHHHB", 0, 0, self.width, self.height, 0))
        self.stream.write(b"\x08")
        for offset in range(0, len(payload), 255):
            block = payload[offset:offset + 255]
            self.stream.write(struct.pack("B", len(block)))
            self.stream.write(block)
        self.stream.write(b"\x00")
        self.frames += 1

    def finish(self):
        if not self.closed:
            if not self.frames:
                raise ValueError("Cannot finish an empty animation")
            self.stream.write(b"\x3b")
            self.closed = True

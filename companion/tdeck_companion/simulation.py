"""Explicit simulation only: never executes a shell or loads an AI model."""

from PIL import Image, ImageDraw

class SimTerminal:
    def __init__(self, target=None):
        self.output = bytearray(b"[SIMULATION: no commands executed]\r\n$ ")
        self.line = bytearray()

    async def start(self):
        return self

    async def read(self, n=4096):
        result = bytes(self.output[:n])
        del self.output[:n]
        return result

    async def write(self, data):
        for b in data:
            if b in (10, 13):
                self.output.extend(b"\r\n[simulated] " + self.line + b"\r\n$ ")
                self.line.clear()
            elif b == 3:
                self.line.clear()
                self.output.extend(b"^C\r\n$ ")
            else:
                self.line.append(b)
                self.output.append(b)

    async def close(self):
        pass

class SimDesktop:
    def __init__(self, *args):
        self.x = 100
        self.y = 80

    async def connect(self):
        return self

    async def snapshot(self):
        im = Image.new("RGB", (640, 480), "#10151d")
        d = ImageDraw.Draw(im)
        for x in range(0, 640, 32):
            d.line((x, 0, x, 480), fill="#283b45")
        for y in range(0, 480, 32):
            d.line((0, y, 640, y), fill="#283b45")
        d.text((12, 12), "SIMULATED DESKTOP - 640 x 480", fill="#32d6a0")
        d.ellipse((self.x - 5, self.y - 5, self.x + 5, self.y + 5), fill="white")
        return im

    async def pointer(self, x, y, buttons=0):
        self.x = x
        self.y = y

    async def key(self, key):
        pass

    async def close(self):
        pass

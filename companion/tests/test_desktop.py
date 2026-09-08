from PIL import Image
from tdeck_companion.desktop import changed_tiles, rgb565be

def test_tile_diff_and_rgb565():
    a = Image.new("RGB", (64, 64))
    b = a.copy()
    b.putpixel((40, 40), (255, 0, 0))
    tiles = changed_tiles(a, b, 32)
    assert len(tiles) == 1
    assert len(rgb565be(tiles[0][1])) == 32 * 32 * 2

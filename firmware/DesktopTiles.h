#pragma once
#include <cstddef>
#include <cstdint>
#include <cstring>
namespace pocketterm
{
// Validate an entire tile batch before writing any framebuffer bytes.
inline bool applyDesktopFrame(const uint8_t *data, size_t size, uint8_t *pixels, size_t pixelBytes, uint16_t &panX,
                              uint16_t &panY)
{
    if (!data || !pixels || size < 10 || pixelBytes < 320u * 176u * 2u || std::memcmp(data, "TDT2", 4))
        return false;
    auto get = [data](size_t p) -> uint16_t { return uint16_t(data[p]) | (uint16_t(data[p + 1]) << 8); };
    unsigned count = get(8);
    if (count > 60)
        return false;
    size_t pos = 10;
    for (unsigned i = 0; i < count; i++)
    {
        if (pos + 8 > size)
            return false;
        unsigned x = get(pos), y = get(pos + 2), w = get(pos + 4), h = get(pos + 6);
        pos += 8;
        if (!w || !h || w > 32 || h > 32 || x + w > 320 || y + h > 176 || pos + 2 * w * h > size)
            return false;
        pos += 2 * w * h;
    }
    if (pos != size)
        return false;
    panX = get(4);
    panY = get(6);
    pos = 10;
    for (unsigned i = 0; i < count; i++)
    {
        unsigned x = get(pos), y = get(pos + 2), w = get(pos + 4), h = get(pos + 6);
        pos += 8;
        for (unsigned yy = 0; yy < h; yy++)
            for (unsigned xx = 0; xx < w; xx++)
            {
                size_t dst = ((y + yy) * 320 + x + xx) * 2;
                pixels[dst] = data[pos + 1];
                pixels[dst + 1] = data[pos];
                pos += 2;
            }
    }
    return true;
}
} // namespace pocketterm

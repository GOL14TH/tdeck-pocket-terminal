#pragma once

#include "configuration.h"

#if HAS_TFT && defined(T_DECK)

#include <Arduino.h>

#include <cstdlib>

#include <cstring>

namespace PocketLink

{

struct Request

{

    String base, token, ca, path, method, body;

    uint32_t generation = 0;

    int action = 0;

    size_t responseLimit = 8192;

};

// Response bodies use PSRAM so desktop traffic cannot exhaust the radio heap.

class ByteBuffer

{

    uint8_t *bytes = nullptr;

    size_t used = 0, capacity = 0;

  public:

    ~ByteBuffer()

    {

        free(bytes);

    }

    bool reserve(size_t n)

    {

        bytes = (uint8_t *)ps_malloc(n);

        if (!bytes && n <= 8192)

            bytes = (uint8_t *)malloc(n);

        capacity = bytes ? n : 0;

        return bytes;

    }

    bool append(const uint8_t *p, size_t n)

    {

        if (used + n > capacity)

            return false;

        memcpy(bytes + used, p, n);

        used += n;

        return true;

    }

    size_t size() const

    {

        return used;

    }

    void clear()

    {

        used = 0;

    }

    uint8_t *data()

    {

        return bytes;

    }

    const uint8_t *data() const

    {

        return bytes;

    }

    uint8_t *begin()

    {

        return bytes;

    }

    uint8_t *end()

    {

        return bytes + used;

    }

    uint8_t operator[](size_t n) const

    {

        return bytes[n];

    }

};

struct Result

{

    uint32_t generation;

    int action, status;

    ByteBuffer data;

    String error;

};

void begin();

bool submit(Request *request);

Result *receive();

} // namespace PocketLink

#endif

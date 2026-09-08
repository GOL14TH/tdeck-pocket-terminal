#include "RemoteProtocol.h"
#include <algorithm>

namespace pocketterm
{
namespace
{
void put16(std::vector<uint8_t> &o, uint16_t v)
{
    o.push_back(v & 0xff);
    o.push_back((v >> 8) & 0xff);
}
void put32(std::vector<uint8_t> &o, uint32_t v)
{
    for (int i = 0; i < 4; ++i)
        o.push_back((v >> (8 * i)) & 0xff);
}
uint16_t get16(const uint8_t *p)
{
    return uint16_t(p[0]) | (uint16_t(p[1]) << 8);
}
uint32_t get32(const uint8_t *p)
{
    return uint32_t(p[0]) | (uint32_t(p[1]) << 8) | (uint32_t(p[2]) << 16) | (uint32_t(p[3]) << 24);
}
} // namespace

uint32_t crc32(const uint8_t *data, size_t len)
{
    uint32_t crc = 0xffffffffu;
    for (size_t i = 0; i < len; ++i)
    {
        crc ^= data[i];
        for (int b = 0; b < 8; ++b)
            crc = (crc >> 1) ^ (0xedb88320u & (0u - (crc & 1u)));
    }
    return ~crc;
}

bool encodeFrame(const Frame &f, std::vector<uint8_t> &out)
{
    if (!f.messageId || f.chunkCount == 0 || f.chunkIndex >= f.chunkCount || f.payload.size() > 0xffff)
        return false;
    out.clear();
    out.reserve(kHeaderSize + f.payload.size());
    put16(out, kMagic);
    out.push_back(kVersion);
    out.push_back(static_cast<uint8_t>(f.kind));
    out.push_back(f.flags);
    out.push_back(0);
    put16(out, f.session);
    put32(out, f.messageId);
    out.push_back(f.chunkIndex);
    out.push_back(f.chunkCount);
    put16(out, static_cast<uint16_t>(f.payload.size()));
    put32(out, crc32(f.payload.data(), f.payload.size()));
    out.insert(out.end(), f.payload.begin(), f.payload.end());
    return true;
}

bool decodeFrame(const uint8_t *data, size_t len, Frame &out)
{
    if (!data || len < kHeaderSize || get16(data) != kMagic || data[2] != kVersion)
        return false;
    const uint16_t payloadLen = get16(data + 14);
    if (len != kHeaderSize + payloadLen)
        return false;
    const uint8_t index = data[12], count = data[13];
    if (!count || index >= count)
        return false;
    const uint32_t msg = get32(data + 8);
    if (!msg)
        return false;
    const uint32_t expected = get32(data + 16);
    if (crc32(data + kHeaderSize, payloadLen) != expected)
        return false;
    out.kind = static_cast<Kind>(data[3]);
    out.flags = data[4];
    out.session = get16(data + 6);
    out.messageId = msg;
    out.chunkIndex = index;
    out.chunkCount = count;
    out.payload.assign(data + kHeaderSize, data + len);
    return true;
}

std::vector<std::vector<uint8_t>> chunkPayload(Kind kind, uint16_t session, uint32_t messageId,
                                               const std::vector<uint8_t> &payload, size_t maxChunkPayload)
{
    std::vector<std::vector<uint8_t>> out;
    if (!messageId || maxChunkPayload == 0 || maxChunkPayload > 0xffff)
        return out;
    size_t n = payload.empty() ? 1 : (payload.size() + maxChunkPayload - 1) / maxChunkPayload;
    if (n > 255)
        return out;
    for (size_t i = 0; i < n; ++i)
    {
        const size_t a = i * maxChunkPayload;
        const size_t b = std::min(payload.size(), a + maxChunkPayload);
        Frame f;
        f.kind = kind;
        f.session = session;
        f.messageId = messageId;
        f.chunkIndex = static_cast<uint8_t>(i);
        f.chunkCount = static_cast<uint8_t>(n);
        if (a < payload.size())
            f.payload.assign(payload.begin() + a, payload.begin() + b);
        std::vector<uint8_t> enc;
        if (!encodeFrame(f, enc))
        {
            out.clear();
            return out;
        }
        out.push_back(std::move(enc));
    }
    return out;
}

std::vector<uint8_t> encodeCommandRequest(const std::string &command, const std::string &args)
{
    if (command.empty() || command.size() > 255 || args.size() > 65535)
        return {};
    std::vector<uint8_t> out;
    out.reserve(3 + command.size() + args.size());
    out.push_back(static_cast<uint8_t>(command.size()));
    out.insert(out.end(), command.begin(), command.end());
    put16(out, static_cast<uint16_t>(args.size()));
    out.insert(out.end(), args.begin(), args.end());
    return out;
}

bool decodeCommandRequest(const std::vector<uint8_t> &p, std::string &command, std::string &args)
{
    if (p.size() < 3)
        return false;
    size_t n = p[0];
    if (!n || p.size() < 1 + n + 2)
        return false;
    uint16_t alen = get16(p.data() + 1 + n);
    if (p.size() != 1 + n + 2 + alen)
        return false;
    command.assign(reinterpret_cast<const char *>(p.data() + 1), n);
    args.assign(reinterpret_cast<const char *>(p.data() + 1 + n + 2), alen);
    return true;
}

std::vector<uint8_t> encodeCommandResult(int16_t status, const std::string &text)
{
    if (text.size() > 65535)
        return {};
    std::vector<uint8_t> out;
    out.reserve(4 + text.size());
    put16(out, static_cast<uint16_t>(status));
    put16(out, static_cast<uint16_t>(text.size()));
    out.insert(out.end(), text.begin(), text.end());
    return out;
}

bool decodeCommandResult(const std::vector<uint8_t> &p, int16_t &status, std::string &text)
{
    if (p.size() < 4)
        return false;
    status = static_cast<int16_t>(get16(p.data()));
    const uint16_t n = get16(p.data() + 2);
    if (p.size() != size_t(4 + n))
        return false;
    text.assign(reinterpret_cast<const char *>(p.data() + 4), n);
    return true;
}

bool Reassembler::ingest(const Frame &f, uint32_t nowMs, Kind &kindOut, uint16_t &sessionOut, uint32_t &messageIdOut,
                         std::vector<uint8_t> &payloadOut)
{
    if (!active_ || f.messageId != messageId_ || f.session != session_ || f.kind != kind_ ||
        f.chunkCount != chunkCount_ || uint32_t(nowMs - startedMs_) > 120000u)
    {
        reset();
        active_ = true;
        kind_ = f.kind;
        session_ = f.session;
        messageId_ = f.messageId;
        chunkCount_ = f.chunkCount;
        startedMs_ = nowMs;
        chunks_.resize(chunkCount_);
        received_.assign(chunkCount_, false);
    }
    if (f.chunkIndex >= chunkCount_)
        return false;
    if (!received_[f.chunkIndex])
    {
        size_t total = f.payload.size();
        for (size_t i = 0; i < chunks_.size(); ++i)
            if (received_[i])
                total += chunks_[i].size();
        if (total > kMaxReassembledPayload)
        {
            reset();
            return false;
        }
        chunks_[f.chunkIndex] = f.payload;
        received_[f.chunkIndex] = true;
    }
    for (bool b : received_)
        if (!b)
            return false;
    payloadOut.clear();
    for (auto &c : chunks_)
        payloadOut.insert(payloadOut.end(), c.begin(), c.end());
    kindOut = kind_;
    sessionOut = session_;
    messageIdOut = messageId_;
    reset();
    return true;
}

void Reassembler::reset()
{
    active_ = false;
    session_ = 0;
    messageId_ = 0;
    chunkCount_ = 0;
    startedMs_ = 0;
    chunks_.clear();
    received_.clear();
}

} // namespace pocketterm

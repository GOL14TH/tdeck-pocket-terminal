#pragma once
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace pocketterm
{

constexpr uint16_t kMagic = 0x5444;
constexpr uint8_t kVersion = 1;
constexpr size_t kHeaderSize = 20;
constexpr size_t kDefaultChunkPayload = 160;
constexpr size_t kMaxReassembledPayload = 4096;

enum class Kind : uint8_t
{
    CommandRequest = 1,
    CommandAck = 2,
    CommandResult = 3,
    CommandError = 4,
};

struct Frame
{
    Kind kind = Kind::CommandRequest;
    uint8_t flags = 0;
    uint16_t session = 0;
    uint32_t messageId = 0;
    uint8_t chunkIndex = 0;
    uint8_t chunkCount = 1;
    std::vector<uint8_t> payload;
};

uint32_t crc32(const uint8_t *data, size_t len);
bool encodeFrame(const Frame &frame, std::vector<uint8_t> &out);
bool decodeFrame(const uint8_t *data, size_t len, Frame &out);
std::vector<std::vector<uint8_t>> chunkPayload(Kind kind, uint16_t session, uint32_t messageId,
                                               const std::vector<uint8_t> &payload,
                                               size_t maxChunkPayload = kDefaultChunkPayload);

std::vector<uint8_t> encodeCommandRequest(const std::string &command, const std::string &args);
bool decodeCommandRequest(const std::vector<uint8_t> &payload, std::string &command, std::string &args);
std::vector<uint8_t> encodeCommandResult(int16_t status, const std::string &text);
bool decodeCommandResult(const std::vector<uint8_t> &payload, int16_t &status, std::string &text);

class Reassembler
{
  public:
    bool ingest(const Frame &frame, uint32_t nowMs, Kind &kindOut, uint16_t &sessionOut, uint32_t &messageIdOut,
                std::vector<uint8_t> &payloadOut);
    void reset();

  private:
    bool active_ = false;
    Kind kind_ = Kind::CommandRequest;
    uint16_t session_ = 0;
    uint32_t messageId_ = 0;
    uint8_t chunkCount_ = 0;
    uint32_t startedMs_ = 0;
    std::vector<std::vector<uint8_t>> chunks_;
    std::vector<bool> received_;
};

} // namespace pocketterm

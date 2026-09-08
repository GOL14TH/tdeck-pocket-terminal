#include "RemoteProtocol.h"
#include <cassert>
#include <iostream>

int main() {
    using namespace pocketterm;
    auto req = encodeCommandRequest("uptime", "--pretty");
    assert(!req.empty());
    std::string cmd, args;
    assert(decodeCommandRequest(req, cmd, args));
    assert(cmd == "uptime" && args == "--pretty");

    std::vector<uint8_t> big(777);
    for (size_t i = 0; i < big.size(); ++i) big[i] = uint8_t(i * 17);
    auto chunks = chunkPayload(Kind::CommandResult, 7, 0x12345678, big, 100);
    assert(chunks.size() == 8);
    Reassembler re;
    Kind k; uint16_t s; uint32_t id; std::vector<uint8_t> joined;
    uint32_t now = 1000;
    for (size_t i = chunks.size(); i-- > 0;) {
        Frame f; assert(decodeFrame(chunks[i].data(), chunks[i].size(), f));
        bool done = re.ingest(f, now++, k, s, id, joined);
        if (i != 0) assert(!done);
        else assert(done);
    }
    assert(k == Kind::CommandResult && s == 7 && id == 0x12345678 && joined == big);

    auto corrupt = chunks[0]; corrupt.back() ^= 0x55;
    Frame bad; assert(!decodeFrame(corrupt.data(), corrupt.size(), bad));

    int16_t status; std::string text;
    auto result = encodeCommandResult(-7, "hello");
    assert(decodeCommandResult(result, status, text));
    assert(status == -7 && text == "hello");
    std::cout << "remote protocol tests: PASS\n";
}

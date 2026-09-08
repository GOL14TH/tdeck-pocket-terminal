#include "PocketMesh.h"
#if HAS_TFT && defined(T_DECK)
#include "MeshService.h"
#include "NodeDB.h"
#include "RemoteProtocol.h"
#include "SinglePortModule.h"
#include "concurrency/OSThread.h"
#include <Preferences.h>
#include <freertos/queue.h>
#include <mbedtls/md.h>
namespace PocketMesh
{
struct Pending
{
    uint32_t dest;
    String key, command, args;
};
static QueueHandle_t outbound = nullptr, inbound = nullptr;
static bool outstanding = false;
static portMUX_TYPE guard = portMUX_INITIALIZER_UNLOCKED;
static void result(const String &s)
{
    String *r = new String(s);
    if (xQueueSend(inbound, &r, 0) != pdTRUE)
        delete r;
}
static void done()
{
    portENTER_CRITICAL(&guard);
    outstanding = false;
    portEXIT_CRITICAL(&guard);
}
class Module : public SinglePortModule, private concurrency::OSThread
{
    Pending *pending = nullptr;
    uint16_t session = 1;
    uint32_t id = 0, nextId = 0, lastSend = 0;
    unsigned tries = 0;
    size_t chunk = 0;
    uint32_t nextChunk = 0;
    std::vector<std::vector<uint8_t>> frames;
    pocketterm::Reassembler rx;
    std::vector<uint8_t> signature(pocketterm::Kind kind, const std::vector<uint8_t> &body)
    {
        uint32_t source = nodeDB->getNodeNum();
        std::vector<uint8_t> data;
        for (int n = 0; n < 4; n++)
            data.push_back(source >> (8 * n));
        data.push_back((uint8_t)kind);
        data.push_back(session);
        data.push_back(session >> 8);
        for (int n = 0; n < 4; n++)
            data.push_back(id >> (8 * n));
        data.insert(data.end(), body.begin(), body.end());
        std::vector<uint8_t> mac(32);
        mbedtls_md_hmac(mbedtls_md_info_from_type(MBEDTLS_MD_SHA256), (const uint8_t *)pending->key.c_str(),
                        pending->key.length(), data.data(), data.size(), mac.data());
        return mac;
    }
    void finish()
    {
        delete pending;
        pending = nullptr;
        frames.clear();
        rx.reset();
        done();
    }

  public:
    Module() : SinglePortModule("PocketMesh", meshtastic_PortNum_PRIVATE_APP), concurrency::OSThread("PocketMesh")
    {
        outbound = xQueueCreate(1, sizeof(Pending *));
        inbound = xQueueCreate(4, sizeof(String *));
        Preferences p;
        p.begin("pocketmesh", false);
        uint32_t boot = p.getUInt("boot", 0) + 1;
        p.putUInt("boot", boot);
        p.end();
        session = (boot % 65535) + 1;
        nextId = esp_random();
    }

  protected:
    int32_t runOnce() override
    {
        if (!pending && xQueueReceive(outbound, &pending, 0) == pdTRUE)
        {
            id = ++nextId;
            if (!id)
                id = ++nextId;
            auto body = pocketterm::encodeCommandRequest(pending->command.c_str(), pending->args.c_str());
            auto mac = signature(pocketterm::Kind::CommandRequest, body);
            body.insert(body.end(), mac.begin(), mac.end());
            frames = pocketterm::chunkPayload(pocketterm::Kind::CommandRequest, session, id, body);
            tries = 1;
            chunk = 0;
            nextChunk = millis();
            lastSend = millis();
        }
        if (pending)
        {
            uint32_t now = millis();
            if (chunk < frames.size() && (int32_t)(now - nextChunk) >= 0)
            {
                auto &bytes = frames[chunk++];
                auto *p = allocDataPacket();
                if (p)
                {
                    p->to = pending->dest;
                    p->channel = 0;
                    p->want_ack = true;
                    p->decoded.payload.size = bytes.size();
                    memcpy(p->decoded.payload.bytes, bytes.data(), bytes.size());
                    service->sendToMesh(p);
                }
                nextChunk = now + 1500;
                lastSend = now;
            }
            else if (chunk == frames.size() && now - lastSend > 45000)
            {
                if (tries >= 3)
                {
                    result("No result after 3 attempts. Execution may have occurred; do not resend a side effect "
                           "blindly.");
                    finish();
                }
                else
                {
                    tries++;
                    chunk = 0;
                    nextChunk = now;
                    lastSend = now;
                    result("Retrying same message ID...");
                }
            }
        }
        return 100;
    }
    ProcessMessage handleReceived(const meshtastic_MeshPacket &mp) override
    {
        if (!pending || mp.from != pending->dest)
            return ProcessMessage::CONTINUE;
        pocketterm::Frame f;
        if (!pocketterm::decodeFrame(mp.decoded.payload.bytes, mp.decoded.payload.size, f) || f.messageId != id ||
            f.session != session)
            return ProcessMessage::CONTINUE;
        pocketterm::Kind kind;
        uint16_t sess;
        uint32_t msg;
        std::vector<uint8_t> payload;
        if (!rx.ingest(f, millis(), kind, sess, msg, payload))
            return ProcessMessage::STOP;
        if (payload.size() < 32)
            return ProcessMessage::STOP;
        std::vector<uint8_t> body(payload.begin(), payload.end() - 32);
        auto mac = signature(kind, body);
        uint8_t different = 0;
        for (int n = 0; n < 32; n++)
            different |= mac[n] ^ payload[payload.size() - 32 + n];
        if (different)
            return ProcessMessage::STOP;
        if (kind == pocketterm::Kind::CommandAck)
        {
            result("Gateway acknowledged; waiting for result");
            lastSend = millis();
        }
        else if (kind == pocketterm::Kind::CommandResult || kind == pocketterm::Kind::CommandError)
        {
            int16_t code;
            std::string text;
            if (pocketterm::decodeCommandResult(body, code, text))
            {
                result(String("Exit ") + String(code) + ": " + String(text.c_str()));
                finish();
            }
        }
        return ProcessMessage::STOP;
    }
};
void setup()
{
    static Module *module = new Module();
    (void)module;
}
bool send(const String &node, const String &key, const String &command, const String &args)
{
    if (!outbound || key.length() < 32 || command.isEmpty() || command.length() > 32 || args.length() > 256)
        return false;
    const char *p = node.c_str();
    if (*p == '!')
        p++;
    char *end = nullptr;
    uint32_t dest = strtoul(p, &end, 16);
    if (!dest || *end || dest == 0xffffffff)
        return false;
    portENTER_CRITICAL(&guard);
    bool was = outstanding;
    outstanding = true;
    portEXIT_CRITICAL(&guard);
    if (was)
        return false;
    Pending *q = new Pending{dest, key, command, args};
    if (xQueueSend(outbound, &q, 0) != pdTRUE)
    {
        delete q;
        done();
        return false;
    }
    return true;
}
String takeResult()
{
    String *p = nullptr;
    if (!inbound || xQueueReceive(inbound, &p, 0) != pdTRUE)
        return "";
    String result = *p;
    delete p;
    return result;
}
} // namespace PocketMesh
#endif

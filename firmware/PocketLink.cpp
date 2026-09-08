#include "PocketLink.h"

#if HAS_TFT && defined(T_DECK)

#include <HTTPClient.h>

#include <WiFi.h>

#include <WiFiClientSecure.h>

#include <freertos/FreeRTOS.h>

#include <freertos/queue.h>

#include <freertos/task.h>

namespace PocketLink

{

static QueueHandle_t requests = nullptr, results = nullptr;

class BoundedSink : public Stream

{

  public:

    ByteBuffer &out;

    bool overflow = false;

    BoundedSink(ByteBuffer &v) : out(v)

    {

    }

    size_t write(uint8_t c) override

    {

        return write(&c, 1);

    }

    size_t write(const uint8_t *p, size_t n) override

    {

        if (!out.append(p, n))

        {

            overflow = true;

            return 0;

        }

        return n;

    }

    int available() override

    {

        return 0;

    }

    int read() override

    {

        return -1;

    }

    int peek() override

    {

        return -1;

    }

    void flush() override

    {

    }

};

static void worker(void *)

{

    for (;;)

    {

        Request *q = nullptr;

        xQueueReceive(requests, &q, portMAX_DELAY);

        Result *r = new Result();

        r->generation = q->generation;

        r->action = q->action;

        r->status = -1;

        if (WiFi.status() != WL_CONNECTED)

            r->error = "Wi-Fi disconnected";

        else if (q->base.startsWith("https://") && q->ca.isEmpty())

            r->error = "HTTPS needs CA certificate (import from SD)";

        else if (!q->base.startsWith("https://") && !q->base.startsWith("http://"))

            r->error = "Use http:// or https:// companion URL";

        else

        {

            HTTPClient http;

            WiFiClient plain;

            WiFiClientSecure tls;

            if (q->ca.length())

                tls.setCACert(q->ca.c_str());

            http.setConnectTimeout(4000);

            http.setTimeout(12000);

            http.setReuse(false);

            bool ok = q->base.startsWith("https://") ? http.begin(tls, q->base + q->path)

                                                     : http.begin(plain, q->base + q->path);

            if (ok)

            {

                http.addHeader("Authorization", "Bearer " + q->token);

                http.addHeader("Content-Type", "text/plain");

                r->status = http.sendRequest(q->method.c_str(), (uint8_t *)q->body.c_str(), q->body.length());

                if (r->status > 0)

                {

                    bool allocated = r->data.reserve(q->responseLimit);

                    BoundedSink sink(r->data);

                    int n = allocated ? http.writeToStream(&sink) : -1;

                    if (n < 0 || sink.overflow)

                    {

                        r->data.clear();

                        r->error = "Incomplete or oversized response";

                        r->status = -1;

                    }

                }

                else

                    r->error = HTTPClient::errorToString(r->status);

                http.end();

            }

            else

                r->error = "Cannot open companion URL";

        }

        delete q;

        xQueueSend(results, &r, portMAX_DELAY);

    }

}

void begin()

{

    if (requests)

        return;

    requests = xQueueCreate(1, sizeof(Request *));

    results = xQueueCreate(1, sizeof(Result *));

    if (!requests || !results || xTaskCreate(worker, "PocketHTTP", 10000, nullptr, 1, nullptr) != pdPASS)

    {

        if (requests)

            vQueueDelete(requests);

        if (results)

            vQueueDelete(results);

        requests = results = nullptr;

    }

}

bool submit(Request *q)

{

    return requests && xQueueSend(requests, &q, 0) == pdTRUE;

}

Result *receive()

{

    Result *r = nullptr;

    if (results)

        xQueueReceive(results, &r, 0);

    return r;

}

} // namespace PocketLink

#endif

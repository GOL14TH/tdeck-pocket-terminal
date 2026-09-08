#include "PocketLauncher.h"

#if HAS_TFT && defined(T_DECK)

#include "DesktopTiles.h"

#include "GPSStatus.h"

#include "NodeDB.h"

#include "PocketLink.h"

#include "PocketMesh.h"

#include "PowerStatus.h"

#include "lvgl.h"

#include "main.h"

#include "ui.h"

#include <Preferences.h>

#include <SD.h>

#include <WiFi.h>

namespace

{

constexpr uint32_t BG = 0x10151d, FG = 0xf2f5f7, ACC = 0x32d6a0, PANEL = 0x243440;

enum Page

{

    HOME,

    HOST,

    AI,

    TERM,

    DESKTOP,

    WIFI,

    FILES,

    MESH,

    SETTINGS

};

enum Action

{

    CHECK = 1,

    AI_START,

    AI_POLL,

    TERM_START,

    TERM_READ,

    TERM_WRITE,

    DESK_START,

    DESK_FRAME,

    DESK_INPUT,

    CLOSE

};

struct Host

{

    String name, base, id, token, node, key;

};

Host hosts[4];

int selected = 0, wifiSlot = 0;

String ca;

Preferences prefs;

lv_obj_t *appScreen = nullptr, *content = nullptr, *statusLabel = nullptr, *output = nullptr, *input = nullptr,

         *canvas = nullptr;

lv_obj_t *fields[7] = {};

lv_group_t *appGroup = nullptr, *stockGroup = nullptr;

Page page = HOME;

uint32_t generation = 0, lastPoll = 0, lastStatus = 0;

bool busy = false, desktopReset = true;

String session, job;

int panX = 0, panY = 0;

uint8_t *framebuffer = nullptr;

uint8_t ansiState = 0;

void show(Page p);

void sendInput(lv_event_t *);

void append(const String &);

String key(const char *prefix, int i)

{

    return String(prefix) + String(i);

}

void status(const String &s)

{

    if (statusLabel)

        lv_label_set_text(statusLabel, s.c_str());

}

void groups(lv_group_t *g)

{

    for (lv_indev_t *d = lv_indev_get_next(nullptr); d; d = lv_indev_get_next(d))

        if (lv_indev_get_type(d) == LV_INDEV_TYPE_KEYPAD || lv_indev_get_type(d) == LV_INDEV_TYPE_ENCODER)

            lv_indev_set_group(d, g);

}

lv_obj_t *label(lv_obj_t *p, const char *s, int x, int y, int w = 300)

{

    auto *l = lv_label_create(p);

    lv_label_set_text(l, s);

    lv_obj_set_pos(l, x, y);

    lv_obj_set_width(l, w);

    lv_obj_set_style_text_color(l, lv_color_hex(FG), 0);

    return l;

}

lv_obj_t *button(lv_obj_t *p, const char *s, int x, int y, int w, lv_event_cb_t cb, void *data = nullptr)

{

    auto *b = lv_button_create(p);

    lv_obj_set_pos(b, x, y);

    lv_obj_set_size(b, w, 28);

    lv_obj_set_style_bg_color(b, lv_color_hex(PANEL), 0);

    lv_obj_set_style_pad_all(b, 3, 0);

    lv_obj_add_event_cb(b, cb, LV_EVENT_CLICKED, data);

    auto *l = lv_label_create(b);

    lv_label_set_text(l, s);

    lv_obj_center(l);

    lv_group_add_obj(appGroup, b);

    return b;

}

lv_obj_t *field(lv_obj_t *p, const char *name, const String &value, int y, int max = 127, bool secret = false)

{

    label(p, name, 4, y + 5, 95);

    auto *t = lv_textarea_create(p);

    lv_obj_set_pos(t, 100, y);

    lv_obj_set_size(t, 207, 31);

    lv_obj_set_style_bg_color(t, lv_color_hex(BG), 0);

    lv_obj_set_style_text_color(t, lv_color_hex(FG), 0);

    lv_textarea_set_one_line(t, true);

    lv_textarea_set_max_length(t, max);

    lv_textarea_set_password_mode(t, secret);

    lv_textarea_set_text(t, value.c_str());

    lv_group_add_obj(appGroup, t);

    return t;

}

String text(lv_obj_t *t)

{

    return String(lv_textarea_get_text(t));

}

String resultText(PocketLink::Result *r)

{

    String s;

    s.reserve(r->data.size() + 1);

    for (auto c : r->data)

        s += (char)c;

    return s;

}

bool request(int action, const String &method, const String &path, const String &body = "")

{

    if (busy)

        return false;

    auto &q = hosts[selected];

    auto *r = new PocketLink::Request();

    r->base = q.base;

    r->token = q.token;

    r->ca = ca;

    r->method = method;

    r->path = path;

    r->body = body;

    r->action = action;

    r->responseLimit = action == DESK_FRAME ? 116000 : 8192;

    r->generation = generation;

    if (!PocketLink::submit(r))

    {

        delete r;

        status("Connection worker unavailable");

        return false;

    }

    busy = true;

    return true;

}

void closeSession()

{

    if (session.length())

        request(CLOSE, "DELETE",

                (page == DESKTOP ? "/api/v2/desktop/session/" : "/api/v1/terminal/session/") + session);

    else if (job.length())

        request(CLOSE, "DELETE", "/api/v2/ai/job/" + job);

    session = "";

    job = "";

}

void navigate(lv_event_t *e)

{

    if (busy)

    {

        status("Finishing request; try again shortly");

        return;

    }

    closeSession();

    show((Page)(intptr_t)lv_event_get_user_data(e));

}

void back(lv_event_t *e)

{

    if (busy)

    {

        status("Finishing request; try again shortly");

        return;

    }

    closeSession();

    show(HOME);

}

void meshUI(lv_event_t *)

{

    if (busy)

        return;

    closeSession();

    lv_screen_load(objects.main_screen);

    groups(stockGroup);

    lv_group_focus_obj(objects.home_button);

}

void home(lv_event_t *)

{

    show(HOME);

}

void append(const String &s)

{

    if (!output)

        return;

    String clean;

    for (size_t i = 0; i < s.length(); ++i)

    {

        char c = s[i];

        if (ansiState == 1)

        {

            ansiState = c == '[' ? 2 : 0;

            continue;

        }

        if (ansiState == 2)

        {

            if (c >= '@' && c <= '~')

                ansiState = 0;

            continue;

        }

        if (c == 27)

        {

            ansiState = 1;

            continue;

        }

        if (c == '\r')

            continue;

        if (c == 8 || c == 127)

        {

            if (clean.length())

                clean.remove(clean.length() - 1);

            else

                lv_textarea_delete_char(output);

            continue;

        }

        if (c == '\n' || c == '\t' || (uint8_t)c >= 32)

            clean += c;

    }

    String all = String(lv_textarea_get_text(output)) + clean;

    if (all.length() > 7000)

        all = all.substring(all.length() - 6000);

    lv_textarea_set_text(output, all.c_str());

    lv_textarea_set_cursor_pos(output, LV_TEXTAREA_CURSOR_LAST);

}

void saveHost(lv_event_t *)

{

    Host h = hosts[selected];

    h.name = text(fields[0]);

    h.base = text(fields[1]);

    while (h.base.endsWith("/"))

        h.base.remove(h.base.length() - 1);

    h.id = text(fields[2]);

    h.token = text(fields[3]);

    h.node = text(fields[4]);

    h.key = text(fields[5]);

    for (size_t i = 0; i < h.id.length(); ++i)

        if (!isalnum(h.id[i]) && h.id[i] != '_' && h.id[i] != '-')

        {

            status("Host ID: letters, digits, - or _ only");

            return;

        }

    if (!h.base.startsWith("http://") && !h.base.startsWith("https://"))

    {

        status("URL must begin http:// or https://");

        return;

    }

    if (h.token.length() < 16)

    {

        status("Token needs at least 16 characters");

        return;

    }

    hosts[selected] = h;

    prefs.putString(key("name", selected).c_str(), h.name);

    prefs.putString(key("base", selected).c_str(), h.base);

    prefs.putString(key("id", selected).c_str(), h.id);

    prefs.putString(key("token", selected).c_str(), h.token);

    prefs.putString(key("node", selected).c_str(), h.node);

    prefs.putString(key("mkey", selected).c_str(), h.key);

    prefs.putInt("selected", selected);

    status("Host saved");

}

void cycleHost(lv_event_t *)

{

    if (busy)

        return;

    selected = (selected + 1) % 4;

    prefs.putInt("selected", selected);

    show(HOST);

}

void checkHost(lv_event_t *)

{

    request(CHECK, "GET", "/api/hosts");

    status("Checking companion...");

}

void importCA(lv_event_t *)

{

    File f = SD.open("/pocket-ca.pem", FILE_READ);

    if (!f || f.size() > 4096)

    {

        status("Put CA PEM at SD /pocket-ca.pem (max 4KB)");

        return;

    }

    String candidate = f.readString();

    f.close();

    if (candidate.indexOf("BEGIN CERTIFICATE") < 0)

    {

        status("Not a PEM certificate");

        return;

    }

    ca = candidate;

    prefs.putString("ca", ca);

    status("CA imported; HTTPS verifies server certificate");

}

void saveWifi(lv_event_t *)

{

    prefs.putString(key("ssid", wifiSlot).c_str(), text(fields[0]));

    prefs.putString(key("psk", wifiSlot).c_str(), text(fields[1]));

    status("Wi-Fi profile saved. Apply restarts device.");

}

void applyWifi(lv_event_t *)

{

    String ssid = text(fields[0]), psk = text(fields[1]);

    if (!ssid.length())

    {

        status("SSID is required");

        return;

    }

    saveWifi(nullptr);

    config.network.wifi_enabled = true;

    strlcpy(config.network.wifi_ssid, ssid.c_str(), sizeof(config.network.wifi_ssid));

    strlcpy(config.network.wifi_psk, psk.c_str(), sizeof(config.network.wifi_psk));

    nodeDB->saveToDisk(SEGMENT_CONFIG);

    rebootAtMsec = millis() + 2000;

    status("Saved to Meshtastic. Restarting in 2 seconds.");

}

void cycleWifi(lv_event_t *)

{

    wifiSlot = (wifiSlot + 1) % 4;

    show(WIFI);

}

void terminalControl(lv_event_t *e)

{

    if (!session.length())

        return;

    char c = (char)(intptr_t)lv_event_get_user_data(e);

    request(TERM_WRITE, "POST", "/api/v1/terminal/session/" + session + "/write", String(c));

}

void pan(lv_event_t *e)

{

    int n = (int)(intptr_t)lv_event_get_user_data(e);

    if (n == 1)

        panX = max(0, panX - 64);

    if (n == 2)

        panX += 64;

    if (n == 3)

        panY = max(0, panY - 64);

    if (n == 4)

        panY += 64;

    desktopReset = true;

}

void desktopPointer(lv_event_t *e)

{

    if (busy || !session.length())

        return;

    auto *d = lv_indev_active();

    if (!d)

        return;

    lv_point_t pt;

    lv_indev_get_point(d, &pt);

    lv_area_t a;

    lv_obj_get_coords(canvas, &a);

    String body = "{\"type\":\"pointer\",\"x\":" + String(panX + constrain(pt.x - a.x1, 0, 319)) +

                  ",\"y\":" + String(panY + constrain(pt.y - a.y1, 0, 175)) + ",\"buttons\":1}";

    request(DESK_INPUT, "POST", "/api/v2/desktop/session/" + session + "/input", body);

}

void desktopKey(lv_event_t *e)

{

    if (busy || !session.length())

        return;

    uint32_t k = lv_event_get_key(e);

    String s;

    if (k == LV_KEY_ENTER)

        s = "enter";

    else if (k == LV_KEY_BACKSPACE)

        s = "bsp";

    else if (k == LV_KEY_LEFT)

        s = "left";

    else if (k == LV_KEY_RIGHT)

        s = "right";

    else if (k == LV_KEY_UP)

        s = "up";

    else if (k == LV_KEY_DOWN)

        s = "down";

    else if (k == LV_KEY_ESC)

        s = "esc";

    else if (k >= 32 && k < 127)

    {

        if (k == '"' || k == '\\')

            s += '\\';

        s += (char)k;

    }

    else

        return;

    request(DESK_INPUT, "POST", "/api/v2/desktop/session/" + session + "/input",

            "{\"type\":\"key\",\"key\":\"" + s + "\"}");

}

void openFile(lv_event_t *)

{

    String path = text(input);

    if (!path.startsWith("/"))

        path = "/" + path;

    File f = SD.open(path, FILE_READ);

    lv_obj_set_style_bg_color(output, lv_color_hex(BG), 0);

    lv_obj_set_style_text_color(output, lv_color_hex(FG), 0);

    lv_textarea_set_text(output, "");

    if (!f)

    {

        append("SD not mounted or path not found.\n");

        return;

    }

    if (f.isDirectory())

    {

        int count = 0;

        File child = f.openNextFile();

        while (child && count++ < 64)

        {

            append(String(child.isDirectory() ? "DIR  " : "FILE ") + child.name() + "\n");

            child.close();

            child = f.openNextFile();

        }

        if (count >= 64)

            append("Listing limited to 64 entries\n");

    }

    else

    {

        size_t n = 0;

        while (f.available() && n++ < 4096)

        {

            char c = f.read();

            if (c == '\n' || c == '\t' || (c >= 32 && c < 127))

                append(String(c));

        }

        if (f.available())

            append("\n[Preview limited to 4KB]");

    }

    f.close();

}

void sendInput(lv_event_t *)

{

    if (busy)

        return;

    String s = text(input);

    if (!s.length())

        return;

    if (page == AI)

    {

        if (job.length())

        {

            request(CLOSE, "DELETE", "/api/v2/ai/job/" + job);

            job = "";

            status("Previous reply closed; press Send again");

            return;

        }

        append("\nYou: " + s + "\n");

        request(AI_START, "POST", "/api/v2/ai/" + hosts[selected].id, s);

    }

    if (page == TERM && session.length())

        request(TERM_WRITE, "POST", "/api/v1/terminal/session/" + session + "/write", s + "\r");

    if (page == MESH)

    {

        int split = s.indexOf(' ');

        String cmd = split < 0 ? s : s.substring(0, split), args = split < 0 ? "" : s.substring(split + 1);

        if (!PocketMesh::send(hosts[selected].node, hosts[selected].key, cmd, args))

        {

            status("Mesh busy or invalid node/key (min 32 chars)");

            return;

        }

        append("\nSent: " + s + "\n");

    }

    lv_textarea_set_text(input, "");

}

void outputArea(int height = 117)

{

    output = lv_textarea_create(content);

    lv_obj_set_pos(output, 2, 2);

    lv_obj_set_size(output, 308, height);

    lv_obj_set_style_bg_color(output, lv_color_hex(BG), 0);

    lv_obj_set_style_text_color(output, lv_color_hex(FG), 0);

    lv_textarea_set_text(output, "");

    lv_obj_set_style_text_font(output, &lv_font_montserrat_10, 0);

    lv_obj_remove_flag(output, LV_OBJ_FLAG_CLICK_FOCUSABLE);

    lv_obj_remove_flag(output, LV_OBJ_FLAG_SCROLL_ON_FOCUS);

}

void show(Page p)

{

    page = p;

    ansiState = 0;

    ++generation;

    output = input = canvas = nullptr;

    for (auto &f : fields)

        f = nullptr;

    lv_group_remove_all_objs(appGroup);

    lv_obj_clean(appScreen);

    statusLabel = label(appScreen, "", 4, 219, 312);

    lv_obj_set_style_text_font(statusLabel, &lv_font_montserrat_10, 0);

    const char *titles[] = {"Pocket Terminal", "Saved hosts", "AI Chat",       "Terminal", "Remote desktop",

                            "Wi-Fi profiles",  "SD files",    "Mesh commands", "Settings"};

    label(appScreen, titles[p], 6, 4, 238);

    button(appScreen, "Back", 253, 0, 61, back);

    content = lv_obj_create(appScreen);

    lv_obj_set_pos(content, 0, 32);

    lv_obj_set_size(content, 320, 184);

    lv_obj_set_style_pad_all(content, 0, 0);

    lv_obj_set_style_border_width(content, 0, 0);

    lv_obj_set_style_bg_color(content, lv_color_hex(BG), 0);

    if (p == HOME)

    {

        button(content, "Meshtastic", 4, 0, 148, meshUI);

        const char *names[] = {"Hosts", "AI chat", "Terminal", "Desktop", "Wi-Fi", "SD files", "Mesh cmd", "Settings"};

        Page dest[] = {HOST, AI, TERM, DESKTOP, WIFI, FILES, MESH, SETTINGS};

        for (int i = 0; i < 8; i++)

        {

            int cell = i + 1;

            button(content, names[i], 4 + (cell % 2) * 156, (cell / 2) * 34, 148, navigate, (void *)(intptr_t)dest[i]);

        }

    }

    else if (p == HOST)

    {

        auto &h = hosts[selected];

        String title = "Profile " + String(selected + 1) + " / 4";

        button(content, title.c_str(), 4, 0, 150, cycleHost);

        fields[0] = field(content, "Name", h.name, 34, 31);

        fields[1] = field(content, "Base URL", h.base, 70, 127);

        fields[2] = field(content, "Host ID", h.id, 106, 31);

        fields[3] = field(content, "Token", h.token, 142, 95, true);

        fields[4] = field(content, "Mesh node", h.node, 178, 10);

        fields[5] = field(content, "Mesh key", h.key, 214, 95, true);

        button(content, "Save", 4, 251, 95, saveHost);

        button(content, "Test link", 105, 251, 95, checkHost);

        button(content, "Import CA", 207, 251, 100, importCA);

        label(content,

              "HTTP: trusted LAN only. HTTPS uses SD CA.\nHost ID selects the companion's saved SSH/AI/VNC host.", 4,

              285);

    }

    else if (p == WIFI)

    {

        String title = "Network " + String(wifiSlot + 1) + " / 4";

        button(content, title.c_str(), 4, 0, 155, cycleWifi);

        fields[0] = field(content, "SSID", prefs.getString(key("ssid", wifiSlot).c_str(), ""), 37, 32);

        fields[1] = field(content, "Password", prefs.getString(key("psk", wifiSlot).c_str(), ""), 73, 63, true);

        button(content, "Save", 4, 112, 105, saveWifi);

        button(content, "Apply + restart", 115, 112, 191, applyWifi);

        label(content, "Meshtastic owns reconnection.\nUse its settings for Bluetooth/radio/GPS.", 4, 149);

    }

    else if (p == AI || p == TERM || p == MESH || p == FILES)

    {

        outputArea();

        input = lv_textarea_create(content);

        lv_obj_set_pos(input, 2, 122);

        lv_obj_set_size(input, 235, 30);

        lv_obj_set_style_bg_color(input, lv_color_hex(BG), 0);

        lv_obj_set_style_text_color(input, lv_color_hex(FG), 0);

        lv_textarea_set_one_line(input, true);

        lv_textarea_set_max_length(input, p == FILES ? 120 : 512);

        lv_group_add_obj(appGroup, input);

        lv_group_focus_obj(input);

        lv_obj_add_event_cb(input, p == FILES ? openFile : sendInput, LV_EVENT_READY, nullptr);

        button(content, p == FILES ? "Open" : "Send", 244, 122, 65, p == FILES ? openFile : sendInput);

        if (p == TERM)

        {

            button(content, "Ctrl-C", 4, 156, 87, terminalControl, (void *)3);

            button(content, "Tab", 99, 156, 75, terminalControl, (void *)9);

            button(content, "Esc", 184, 156, 75, terminalControl, (void *)27);

            request(TERM_START, "POST", "/api/v1/terminal/" + hosts[selected].id);

        }

        if (p == MESH)

            append("Allowlisted commands only.\nSet gateway node + key in Hosts.\n");

        if (p == FILES)

        {

            lv_textarea_set_text(input, "/");

            openFile(nullptr);

        }

    }

    else if (p == DESKTOP)

    {

        if (!framebuffer)

            framebuffer = (uint8_t *)ps_malloc(320 * 176 * 2);

        if (framebuffer)

        {

            memset(framebuffer, 0, 320 * 176 * 2);

            canvas = lv_canvas_create(content);

            lv_canvas_set_buffer(canvas, framebuffer, 320, 176, LV_COLOR_FORMAT_RGB565);

            lv_obj_add_flag(canvas, LV_OBJ_FLAG_CLICKABLE);

            lv_group_add_obj(appGroup, canvas);

            lv_group_focus_obj(canvas);

            lv_obj_add_event_cb(canvas, desktopPointer, LV_EVENT_CLICKED, nullptr);

            lv_obj_add_event_cb(canvas, desktopKey, LV_EVENT_KEY, nullptr);

            // Pan controls overlay only the bottom edge of the viewport.

            button(content, "<", 2, 151, 32, pan, (void *)1);

            button(content, ">", 38, 151, 32, pan, (void *)2);

            button(content, "^", 74, 151, 32, pan, (void *)3);

            button(content, "v", 110, 151, 32, pan, (void *)4);

            panX = panY = 0;

            desktopReset = true;

            request(DESK_START, "POST", "/api/v2/desktop/" + hosts[selected].id);

        }

        else

            label(content, "Not enough PSRAM for desktop", 4, 10);

    }

    else if (p == SETTINGS)

    {

        button(content, "Meshtastic settings", 4, 5, 300, meshUI);

        button(content, "Saved hosts", 4, 42, 300, navigate, (void *)HOST);

        button(content, "Saved Wi-Fi", 4, 79, 300, navigate, (void *)WIFI);

        label(content,

              "Display, input, power, GPS and radio\nsettings remain in the Meshtastic UI.\nRemote desktop: tap/click, "

              "keys, pan arrows.",

              4, 119);

    }

    lv_screen_load(appScreen);

    groups(appGroup);

    lastPoll = millis();

}

void receive()

{

    auto *r = PocketLink::receive();

    if (!r)

        return;

    busy = false;

    if (r->generation != generation)

    {

        delete r;

        return;

    }

    if (r->status < 200 || r->status >= 300)

    {

        if (r->action == DESK_FRAME)

            desktopReset = true;

        String err = r->error.length() ? r->error : resultText(r);

        status("Link " + String(r->status) + ": " + err.substring(0, 75));

        if (output)

            append("\nError: " + err.substring(0, 180) + "\n");

        if (r->status == 404)

        {

            session = "";

            job = "";

        }

        lastPoll = millis() + 3000;

        delete r;

        return;

    }

    String t;

    if (r->action != DESK_FRAME)

        t = resultText(r);

    switch (r->action)

    {

    case CHECK:

        status(t.indexOf("\"simulation\":true") >= 0 ? "Connected to SIMULATED companion" : "Companion authenticated");

        break;

    case AI_START:

        job = t;

        status("AI working...");

        break;

    case AI_POLL:

        if (r->status == 200)

        {

            append("AI: " + t + "\n");

            request(CLOSE, "DELETE", "/api/v2/ai/job/" + job);

            job = "";

            status("Reply received");

        }

        break;

    case TERM_START:

        session = t;

        status("Terminal connected");

        break;

    case TERM_READ:

        append(t);

        break;

    case DESK_START:

        session = t;

        status("Desktop connected");

        break;

    case DESK_FRAME: {

        uint16_t x = 0, y = 0;

        if (canvas && pocketterm::applyDesktopFrame(r->data.data(), r->data.size(), framebuffer, 320 * 176 * 2, x, y))

        {

            panX = x;

            panY = y;

            lv_obj_invalidate(canvas);

            desktopReset = false;

        }

        else

        {

            desktopReset = true;

            status("Invalid desktop frame; requesting refresh");

        }

        break;

    }

    default:

        break;

    }

    delete r;

}

} // namespace

namespace PocketLauncher

{

void task()

{

    if (!appScreen && objects.main_screen && objects.home_button)

    {

        prefs.begin("pocket2", false);

        selected = constrain(prefs.getInt("selected", 0), 0, 3);

        ca = prefs.getString("ca", "");

        for (int i = 0; i < 4; i++)

        {

            auto &h = hosts[i];

            h.name = prefs.getString(key("name", i).c_str(), "Pi");

            h.base = prefs.getString(key("base", i).c_str(), "http://tdeckpi.local:8787");

            h.id = prefs.getString(key("id", i).c_str(), "pi");

            h.token = prefs.getString(key("token", i).c_str(), "");

            h.node = prefs.getString(key("node", i).c_str(), "");

            h.key = prefs.getString(key("mkey", i).c_str(), "");

        }

        stockGroup = lv_group_get_default();

        appGroup = lv_group_create();

        appScreen = lv_obj_create(nullptr);

        lv_obj_set_style_bg_color(appScreen, lv_color_hex(BG), 0);

        lv_obj_set_style_text_font(appScreen, &lv_font_montserrat_16, 0);

        lv_obj_set_style_pad_all(appScreen, 0, 0);

        lv_obj_remove_flag(appScreen, LV_OBJ_FLAG_SCROLLABLE);

        auto *b = lv_button_create(objects.main_screen);

        lv_obj_set_size(b, 48, 24);

        lv_obj_align(b, LV_ALIGN_TOP_RIGHT, -2, 2);

        auto *l = lv_label_create(b);

        lv_label_set_text(l, "Apps");

        lv_obj_center(l);

        lv_obj_add_event_cb(b, home, LV_EVENT_CLICKED, nullptr);

        if (stockGroup)

            lv_group_add_obj(stockGroup, b);

        PocketLink::begin();

        show(HOME);

    }

    if (!appScreen)

        return;

    receive();

    String message = PocketMesh::takeResult();

    if (message.length() && page == MESH)

        append(message + "\n");

    if (lv_screen_active() != appScreen)

        return;

    uint32_t now = millis();

    if (!busy && (int32_t)(now - lastPoll) >= 700)

    {

        lastPoll = now;

        if (page == AI && job.length())

            request(AI_POLL, "GET", "/api/v2/ai/job/" + job);

        if (page == TERM && session.length())

            request(TERM_READ, "GET", "/api/v1/terminal/session/" + session + "/read");

        if (page == DESKTOP && session.length())

            request(DESK_FRAME, "GET",

                    "/api/v2/desktop/session/" + session + "/frame?x=" + String(panX) + "&y=" + String(panY) +

                        "&reset=" + (desktopReset ? "true" : "false"));

    }

    if (page == HOME && now - lastStatus > 2000)

    {

        lastStatus = now;

        time_t tm = time(nullptr);

        struct tm local;

        localtime_r(&tm, &local);

        char buf[110];

        snprintf(buf, sizeof(buf), "B%d%% WiFi:%s GPS:%s %02d:%02d | %s",

                 powerStatus ? powerStatus->getBatteryChargePercent() : 0, WiFi.status() == WL_CONNECTED ? "ON" : "OFF",

                 gpsStatus && gpsStatus->getHasLock() ? "FIX" : "--", local.tm_hour, local.tm_min,

                 hosts[selected].name.c_str());

        status(buf);

    }

}

} // namespace PocketLauncher

#endif

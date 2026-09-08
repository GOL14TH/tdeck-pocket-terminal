"""Apply the LVGL integration to the pinned Meshtastic 2.7.15 source tree."""

from pathlib import Path

import argparse, shutil

ROOT = Path(__file__).resolve().parents[1]

def apply(upstream):

    upstream = Path(upstream).resolve()

    tft = upstream / "src/graphics/tftSetup.cpp"

    modules = upstream / "src/modules/Modules.cpp"

    if not tft.exists() or not modules.exists():

        raise SystemExit("Expected Meshtastic source tree")

    ts = tft.read_text()

    ms = modules.read_text()

    if "PocketLauncher::task();" not in ts:

        anchor = "        deviceScreen->task_handler();"

        if anchor not in ts:

            raise SystemExit("Unexpected TFT API; refusing an unverified patch")

        ts = ts.replace(

            anchor,

            anchor + "\n#if defined(T_DECK)\n        PocketLauncher::task();\n#endif",

            1,

        )

    if '#include "graphics/PocketLauncher.h"' not in ts:

        ts = ts.replace(

            '#include "graphics/DeviceScreen.h"',

            '#include "graphics/DeviceScreen.h"\n#include "graphics/PocketLauncher.h"',

            1,

        )

    if "PocketMesh::setup();" not in ms:

        anchor = "    routingModule = new RoutingModule();"

        if anchor not in ms:

            raise SystemExit("Unexpected module registration API")

        ms = ms.replace(

            anchor,

            "#if HAS_TFT && defined(T_DECK)\n    PocketMesh::setup();\n#endif\n"

            + anchor,

            1,

        )

    if '#include "graphics/PocketMesh.h"' not in ms:

        ms = ms.replace(

            '#include "configuration.h"',

            '#include "configuration.h"\n#if HAS_TFT && defined(T_DECK)\n#include "graphics/PocketMesh.h"\n#endif',

            1,

        )

    for source in (ROOT / "firmware").iterdir():

        if source.suffix in (".cpp", ".h"):

            shutil.copy2(source, upstream / "src/graphics" / source.name)

    if tft.read_text() != ts:

        tft.write_text(ts)

    if modules.read_text() != ms:

        modules.write_text(ms)

    build = upstream / "bin/platformio-custom.py"

    bs = build.read_text()

    if "TDECK_BUILD_REPO" not in bs:

        bs = bs.replace(

            'jsonLoc = env["PROJECT_DIR"]',

            'repo_owner = os.environ.get("TDECK_BUILD_REPO", repo_owner)\n\njsonLoc = env["PROJECT_DIR"]',

            1,

        )

        if "import os\n" not in bs:

            bs = bs.replace("import sys", "import sys\nimport os", 1)

        bs = bs.replace(

            "build_epoch = int(current_date.timestamp())",

            'build_epoch = int(os.environ.get("SOURCE_DATE_EPOCH", current_date.timestamp()))',

        )

        build.write_text(bs)

    print("Applied Pocket Terminal LVGL integration; no firmware written to a device.")

if __name__ == "__main__":

    ap = argparse.ArgumentParser()

    ap.add_argument("upstream")

    apply(ap.parse_args().upstream)

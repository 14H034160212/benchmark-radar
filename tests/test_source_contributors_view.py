"""A published cross-source duplicate is not an unranked source failure."""

import json
import shutil
import subprocess
from pathlib import Path


def test_zero_source_status_recognizes_contributors_and_legacy_primary_counts():
    node = shutil.which("node")
    assert node, "Node.js is required for the site behavior tests"
    script = Path("site/assets/app.js").read_text()
    start = script.index("const SOURCE_DISPLAY_NAMES =")
    end = script.index("// Why the Today list is empty", start)
    harness = (
        'import {readFileSync} from "node:fs";\n'
        + script[start:end]
        + "\nconsole.log(JSON.stringify(JSON.parse(readFileSync(0, 'utf8')).map(zeroItemSources)));"
    )
    health = [{"source": "xbsleepy", "ok": True, "item_count": 1}]
    days = [
        {
            "source_counts": {"arXiv": 1},
            "contributing_source_counts": {"arXiv": 1, "XBsleepy": 1},
            "ingest_health": health,
        },
        {"source_counts": {"XBsleepy": 1}, "ingest_health": health},
        {"source_counts": {}, "ingest_health": health},
    ]
    result = subprocess.run(
        [node, "--input-type=module", "-e", harness],
        input=json.dumps(days),
        capture_output=True,
        text=True,
        check=True,
    )
    outputs = json.loads(result.stdout)
    assert outputs[:2] == [[], []]
    assert outputs[2] == [{"name": "XBsleepy", "ok": True, "fetched": 1, "state": "unranked"}]

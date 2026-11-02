"""Generate the perf-seed template files and ZIPs from templates.py and connectors.py.

    python3 perf/seed/build.py

Writes perf/seed/generated/templates/<key>/ (BPMN, DMN, form schemas) plus
<key>.zip ready for POST /templates/import, and
perf/seed/generated/connectors/<model>/ for the stand-alone connector models.
The generated tree is checked in so the seed runs without a build step;
re-run this after editing the Python sources.
"""

from __future__ import annotations

import json
import shutil
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from connectors import all_connector_models
from templates import all_templates

OUT = HERE / "generated"


def write_model_dir(target: Path, bpmn_name: str, bpmn_xml: str, dmn: tuple[str, str] | None,
                    forms: dict[str, dict]) -> list[Path]:
    target.mkdir(parents=True, exist_ok=True)
    files = [target / bpmn_name]
    files[0].write_text(bpmn_xml)
    if dmn:
        files.append(target / dmn[0])
        files[-1].write_text(dmn[1])
    for base, spec in forms.items():
        for suffix in ("schema", "uischema"):
            path = target / f"{base}-{suffix}.json"
            path.write_text(json.dumps(spec[suffix], indent=2) + "\n")
            files.append(path)
    return files


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    for template in all_templates():
        target = OUT / "templates" / template.key
        files = write_model_dir(target, template.bpmn_file, template.diagram.to_xml(), template.dmn, template.forms)
        zip_path = OUT / "templates" / f"{template.key}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in files:
                # fixed timestamp keeps the ZIP byte-identical across rebuilds
                info = zipfile.ZipInfo(path.name, date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                zf.writestr(info, path.read_bytes())
        print(f"template  {template.key:<24} {len(files)} files -> {zip_path.relative_to(HERE)}")
    for model in all_connector_models():
        target = OUT / "connectors" / model.model_id
        files = write_model_dir(target, model.bpmn_file, model.diagram.to_xml(), None, model.forms)
        print(f"connector {model.model_id:<24} {len(files)} files")


if __name__ == "__main__":
    main()

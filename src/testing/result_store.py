import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from ..utils.errors import FrameworkError

RUN_ID_PATTERN = re.compile(r"^\d{8}T\d{6}Z-[0-9a-f]{8}$")
LATEST = "latest"


class ResultStoreError(FrameworkError):
    """
    Raised when a run cannot be saved or found, or its file is unreadable.
    """


def new_run_id() -> str:
    """
    Returns a unique, chronologically sortable run id such as 20261027T101500Z-a1b2c3d4.
    """
    return f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"


class ResultStore:
    """
    Archives each test run as one JSON file named after its run id.
    """

    def __init__(self, directory: str):
        """
        Stores the archive directory; it is created on the first save.
        """
        self._directory = Path(directory)

    def save(self, run: Dict) -> Path:
        """
        Writes the run to <directory>/<run_id>.json, never overwriting an existing run. The file appears complete or not at all.
        """
        path = self._path(run["run_id"])
        if path.exists():
            raise ResultStoreError(f"run {run['run_id']} already exists")

        # Write to a temporary file first, then move it into place
        temp = path.with_suffix(".tmp")
        try:
            self._directory.mkdir(parents=True, exist_ok=True)
            temp.write_text(json.dumps(run, indent=2), encoding="utf-8")
            os.replace(temp, path)
        except OSError as exc:
            temp.unlink(missing_ok=True)
            raise ResultStoreError(f"cannot save run {run['run_id']}: {exc.strerror or exc}") from exc

        return path

    def load(self, run_id: str) -> Dict:
        """
        Returns the archived run with this id, or the newest one for "latest".
        """
        if run_id == LATEST:
            ids = self.run_ids()
            if not ids:
                raise ResultStoreError(f"no runs archived in {self._directory}")
            run_id = ids[-1]

        path = self._path(run_id)
        if not path.exists():
            raise ResultStoreError(f"run {run_id} not found in {self._directory}")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ResultStoreError(f"run {run_id} is corrupt: {exc}") from exc
        except OSError as exc:
            raise ResultStoreError(f"cannot read run {run_id}: {exc.strerror or exc}") from exc

    def run_ids(self) -> List[str]:
        """
        Returns the ids of all archived runs, oldest first.
        """
        if not self._directory.exists():
            return []

        return sorted(p.stem for p in self._directory.glob("*.json") if RUN_ID_PATTERN.match(p.stem))

    def list_runs(self) -> List[Dict]:
        """
        Returns a short summary (id, time, label, ammeters) of every readable run, oldest first.
        """
        summaries = []
        for run_id in self.run_ids():
            try:
                run = self.load(run_id)
            except ResultStoreError:
                continue
            metadata = run["metadata"]
            summaries.append({"run_id": run_id, "created_at": metadata["created_at"], "label": metadata["label"], "ammeters": [a["ammeter"] for a in run["ammeters"]]})

        return summaries

    def _path(self, run_id: str) -> Path:
        """
        Returns the file path for a run id, rejecting ids that are not in the generated format (blocks path tricks like ../x).
        """
        if not RUN_ID_PATTERN.match(run_id):
            raise ResultStoreError(f"invalid run id '{run_id}'")

        return self._directory / f"{run_id}.json"

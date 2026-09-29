"""E19 publish — validate invariants, compute table digests and the result digest, write the manifest.

The orchestrator closes the store and makes it read-only afterwards (I3). `run_id` is provenance, not
content, so it is excluded from digests: the same inputs give the same result digest (I4).
"""

from __future__ import annotations

import json

from sutradhar_engine.digest import combine, table_digest
from sutradhar_engine.runner import RunContext, RunError, StageReport, code_version
from sutradhar_schemas.evidence import RunManifest

RESULT_TABLES: dict[str, tuple[str, ...]] = {
    "d_tx": ("tx_i",),
    "d_addr": ("addr_i",),
    "d_ip": ("ip_i",),
    "lead": ("lead_i",),
}


class PublishStage:
    code = "E19"
    name = "publish"
    requires = ("lead",)
    produces = ()

    def run(self, ctx: RunContext) -> StageReport:
        con = ctx.con
        bad = con.execute(
            "SELECT count(*) FROM lead WHERE json_array_length(reasons) < 1 OR json_array_length(families) < 1 OR p < 0 OR p > 1"
        ).fetchone()[0]  # type: ignore[index]
        if bad:
            raise RunError("E19", f"{bad} lead(s) violate I6 (reasons, families, probability range)")
        present = [
            t
            for t in RESULT_TABLES
            if con.execute(
                "SELECT count(*) FROM information_schema.tables WHERE table_name = ?", [t]
            ).fetchone()[0]
        ]  # type: ignore[index]
        digests = {t: table_digest(con, t, RESULT_TABLES[t], exclude=("run_id",)) for t in present}
        result_digest = combine(digests)
        ds = ctx.dataset_manifest
        manifest = RunManifest(
            run_id=ctx.run_id,
            dataset={
                "id": ds["dataset_id"],
                "raw_digest": ds["raw_digest"],
                "normalised_digest": ds["normalised_digest"],
                "profile": ds["profile_ref"],
                "profile_sha256": ds["profile_sha256"],
            },
            code=code_version(),
            config={
                "seed": ctx.settings.seed,
                "threads": ctx.settings.threads,
                "settings_sha256": ctx.settings.sha256(),
            },
            stages=ctx.stats,
            result_tables=present,
            result_digest=result_digest,
        )
        ctx.meta["manifest"] = manifest.model_dump(mode="json")
        ctx.meta["table_digests"] = digests
        ctx.put_meta("manifest", ctx.meta["manifest"])
        ctx.put_meta("table_digests", digests)
        (ctx.run_dir / "manifest.json").write_text(
            json.dumps(ctx.meta["manifest"], indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return StageReport(
            rows={"result_tables": len(present)}, notes=[f"result digest {result_digest[:16]}…"]
        )


STAGE = PublishStage()

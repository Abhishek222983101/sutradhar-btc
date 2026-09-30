# Writing an analysis stage

A stage is a small object that reads tables from the run, writes a table, and reports what it did. Any Python package can
ship one; Sutradhar finds it through an entry point and runs it just before lead ranking.

```python
# my_plugin/stage.py
from sutradhar_engine.runner import RunContext, StageReport


class BigSweeps:
    code = "XSWEEP"  # plugin codes start with X, so they never collide with E01-E19
    name = "very large consolidations"
    requires = ("cluster",)  # tables that must exist before this stage runs
    produces = ("big_sweeps",)  # tables this stage must create (checked after it runs)

    def run(self, ctx: RunContext) -> StageReport:
        ctx.con.execute("""
            CREATE TABLE big_sweeps AS
            SELECT txid, n_in FROM ds.tx WHERE n_in >= 50 AND n_out <= 2   -- ds.* is the immutable dataset
        """)
        n = ctx.con.execute("SELECT count(*) FROM big_sweeps").fetchone()[0]
        return StageReport(rows={"big_sweeps": n})
```

```toml
# my_plugin/pyproject.toml
[project.entry-points."sutradhar.stages"]
sweeps = "my_plugin.stage:BigSweeps"
```

Install the package next to Sutradhar and the stage appears in every run's manifest and in the console's pipeline view.

Rules the runner enforces:

* The stage may only read the dataset (`ds.*`) and earlier run tables; the dataset is attached read-only.
* A stage that does not create every table in `produces` fails the run with a clear message.
* Plugins that fail to load, or whose code does not start with `X`, are skipped with a log line and never stop a run.
* Runs stay reproducible: use `ctx.settings.seed` for randomness and order every result explicitly.

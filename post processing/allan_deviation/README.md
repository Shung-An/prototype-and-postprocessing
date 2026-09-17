# Allan-deviation tools and results

This folder contains the Allan-specific scripts, tests, method notes, plots,
presentation exports, logs, and historical backups.

- `allan_deviation_analysis.py`: batch and per-run long-term analysis.
- `plot_allan_slope_example.py`: individual curves and tail fits.
- `plot_allan_presentation.py`: raw-frame millisecond analysis and per-pair plots.
- `plot_allan_mean_presentation.py`: merged mean curve with square axes and bold text.
- `plot_allan_batch_summary.py`: cross-run summary plots.
- `compare_allan_stability.py`: fixed-position Allan/mean comparison.
- `presentation_20260807_203712/` and `presentation_20260910_170948/`: presentation exports and supporting data.
- `allan_stability_20260817_160256/`: fixed-position comparison results.

See [the analysis method](ALLAN_DEVIATION_METHOD.md) for units and assumptions.
The shared `cm_pipeline_all_in_one.py` and browser remain in the parent folder.
Original measurement files and per-run browser outputs remain in DataFiles.

From the repository root:

```powershell
python 'post processing/allan_deviation/allan_deviation_analysis.py' --help
python -m unittest discover -s 'post processing/allan_deviation' -p 'test_allan_variance.py'
```

Reproduce a mean presentation from its saved inputs and condition lines:

```python
import json
import subprocess
import sys
from pathlib import Path

folder = Path('post processing/allan_deviation')
output = folder / 'presentation_20260910_170948' / 'allan_deviation_presentation'
report = json.loads(output.with_suffix('.json').read_text(encoding='utf-8'))
command = [sys.executable, str(folder / 'plot_allan_mean_presentation.py'),
           report['run'], '--millisecond-csv', str(output.with_suffix('.csv')),
           '--output', str(output)]
for condition in report.get('experiment_conditions', []):
    command.extend(['--condition', condition])
subprocess.run(command, check=True)
```

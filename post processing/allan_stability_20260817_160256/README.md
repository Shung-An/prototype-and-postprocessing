# Allan variance trial

Source: `D:\Quantum Squeezing Project\DataFiles\20260817_160256`.
Metadata describes a fixed-position (scan range 0 mm) CeF3 measurement,
"highpass + bandpass + attenuator, stay, CeF3", tagged Alignment.
This is a stationary measurement trial; no run explicitly tagged Stability was found.
The source dataset was read without modifying its outputs.

`mean_vs_allan.pdf` and `mean_vs_allan.png` compare the former absolute cumulative
mean with overlapping Allan variance for the same nine pairs selected by the
pipeline's endpoint-channel MSE ranking. `loglog_eval.png` is the new main plot.
`allan_variance.csv` includes variance, deviation, averaging factor and overlapping
term counts. `summary.json` records source, scaling and numerical results.

The 120,322 frames cover 1,658.42 seconds of nominal acquisition time. Tau runs
from 0.013783 to 165.84 seconds, limited to one tenth of the record. Transfer
timestamps include duplicates and software scheduling jitter, so the calculation
uses the existing acquisition interval 67/4861 seconds per frame. This assumes
consecutive acquisition frames; unrecorded acquisition loss or dead time cannot
be inferred from these transfer timestamps. Tau is not wall-clock elapsed time.

All nine curves decrease at long averaging times; slopes fitted over the last
ten tau points range from -0.89 to -0.80. A shared bump appears near 0.4 seconds.
There is no visible long-tau plateau or rising drift tail in the evaluated range.
The two panels have different units and time-axis meanings; their heights cannot
be compared directly. No curve smoothing or detrending was applied.

For measured pair differences y, the estimator is
`AVAR(tau) = mean((mean(y[i+m:i+2m]) - mean(y[i:i+m]))**2) / 2`,
using every valid starting index, with `tau = m * frame_dt`.
Scaling is applied before squaring: measurements in µrad² yield variance in µrad⁴.
Constant residuals cancel. Noise and time-dependent changes remain, so an Allan
tail is not exclusively drift. Pure linear drift of slope d contributes
`d² tau² / 2`; converting a measured tail to a drift rate requires evidence that
this model dominates. The full-record linear slopes in the JSON are descriptive
fits, without a claim of statistical significance. Overlapping counts are not
independent degrees of freedom and no confidence intervals are claimed.

Suggested thesis caption: "Absolute cumulative mean and overlapping Allan
variance of nine selected correlation-channel differences in a fixed-position
CeF3 measurement. Allan variance cancels constant offsets and shows decreasing
long-time fluctuations up to 166 s averaging time, with a shared subsecond bump.
Averaging times use the nominal acquisition cadence; curves are not detrended."

Method reference: [NIST Handbook of Frequency Stability Analysis](https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication1065.pdf).

Reproduce from the repository root:

```powershell
python 'post processing/compare_allan_stability.py' 'D:\Quantum Squeezing Project\DataFiles\20260817_160256' 'post processing/allan_stability_20260817_160256'
python -m unittest discover -s 'post processing' -p 'test_allan_variance.py'
```

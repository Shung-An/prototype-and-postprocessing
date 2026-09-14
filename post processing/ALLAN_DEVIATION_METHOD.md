# Allan-Deviation Analysis Method

## Purpose

This analysis measures how the difference between two covariance-matrix channels
changes with averaging time. It is intended to separate a constant residual
offset from time-dependent fluctuations and to identify the averaging time beyond
which stability stops improving.

The analyzed quantity is a measured covariance difference, not clock frequency
or phase. Standard Allan-variance slope names are therefore used only as
descriptive labels for the observed curves.

## Input quantity and units

For candidate pair (p), the time series is

\[
y_{p,k}=C_{a_p,k}-C_{b_p,k},
\]

where (C_{a_p,k}) and (C_{b_p,k}) are two covariance-matrix channels at sample
(k). The channel-pair labels use the form
`(row1,column1)-(row2,column2)`.

Raw covariance values are scaled by the detector-area factor and, when enabled,
the power-detector attenuation correction. Runs displayed in angular units use

\[
y_{p,k}^{(\mu\mathrm{rad}^2)}=
\frac{y_{p,k}^{(\mathrm{V}^2)}}{K_{\mathrm{V}^2/\mathrm{rad}^2}}10^{12},
\]

where (K) is the conversion factor stored in the run metadata. Allan deviation
has the same unit as (y): either (mathrm{V}^2) or
(\mu\mathrm{rad}^2). Allan variance has the corresponding squared unit:
(mathrm{V}^4) or (\mu\mathrm{rad}^4).

## Long-term preprocessing

The batch analyzer in `allan_deviation_analysis.py` averages consecutive raw
frames before calculating Allan deviation. For the default target base time of
1 s, the number of frames in one base bin is

\[
B=\operatorname{round}\!\left(\frac{1\ \mathrm{s}}{\Delta t_{\mathrm{frame}}}\right),
\qquad
\Delta t_{\mathrm{frame}}=\frac{67}{4861}\ \mathrm{s}
\approx 0.0137832\ \mathrm{s}.
\]

Thus the default is (B=73) frames, giving a nominal base-bin duration of about
1.00617 s. If an acquisition is too short, (B) is reduced so at least ten base
samples remain. An incomplete final bin is discarded and recorded as
`DroppedTailFrames`.

The timestamp for each base bin is the mean of its constituent frame timestamps.
The analyzer uses timestamps parsed from `profile.txt` when they are complete and
strictly increasing. Missing timestamps are filled using the nominal frame
cadence. If the resulting base-bin times are invalid, the entire time axis falls
back to the nominal acquisition cadence. The source and measured cadence are
recorded in metadata as `TimestampSource` and `MedianBaseCadence_s`.

## Pair selection

The analyzer considers the pipeline's fixed candidate-pair list. It computes the
variance of every pre-averaged covariance channel and assigns pair (p) the mean
variance of its two endpoints:

\[
S_p=\frac{\operatorname{Var}(C_{a_p})+
                 \operatorname{Var}(C_{b_p})}{2}.
\]

The nine pairs with the largest finite (S_p) values are analyzed by default.
This selects channels with the strongest long-term variation; it does not select
the pairs with the lowest Allan deviation.

## Overlapping Allan variance and deviation

Let (y_0,\ldots,y_{N-1}) be one selected, pre-averaged pair-difference series.
For averaging factor (m), define the (m)-sample moving average

\[
\bar y_i^{(m)}=\frac{1}{m}\sum_{j=0}^{m-1}y_{i+j}.
\]

The overlapping Allan variance used in the code is

\[
\sigma_y^2(\tau)=
\frac{1}{2M}
\sum_{i\in\mathcal V}
\left(\bar y_{i+m}^{(m)}-\bar y_i^{(m)}\right)^2,
\]

and Allan deviation is

\[
\sigma_y(\tau)=\sqrt{\sigma_y^2(\tau)}.
\]

Here

\[
\tau=m\,\widetilde{\Delta t},
\]

where (\widetilde{\Delta t}) is the median base-sample cadence. The valid-index
set (\mathcal V) contains every possible starting index whose complete (2m)
sample interval contains finite values and crosses no detected timing gap. (M)
is the number of these valid overlapping terms. A timing step below 0.5 or above
1.5 times the median cadence is treated as a gap.

The implementation uses cumulative sums for efficiency, but this is algebraically
the same estimator shown above. It subtracts a constant center before forming the
cumulative sums to improve numerical precision. That centering does not detrend
the data and does not change the Allan variance.

## Averaging-time grid and long-time limit

The averaging factors are unique logarithmically spaced integers from (m=1) to

\[
m_{\max}=\left\lfloor\frac{N}{10}\right\rfloor,
\]

with at most 60 values by default. The (N/10) limit retains at least ten nominal
averaging blocks at the largest tested (\tau). `overlapping_terms` is the number
of overlapping differences actually used; it is not the number of statistically
independent observations. The CSV also reports

\[
N_{\mathrm{blocks,nominal}}=\left\lfloor\frac{N}{m}\right\rfloor.
\]

No confidence interval is currently calculated. The longest reported point is
therefore called the longest *reliable by the nominal-block rule* rather than a
formal uncertainty bound.

## Reported summary values

For each selected pair, the analysis reports:

- `MinimumAllanDeviation`: the smallest finite positive value on the tested grid.
- `TauAtMinimum_s`: the tested (\tau) at that minimum.
- `AllanDeviationAtLongestTau`: the value at the final valid tested (\tau).
- `LongestTau_s`: that final tested averaging time.
- `LongTermToMinimumRatio`: longest-time deviation divided by the minimum.
- `LongTermLogSlope`: a least-squares slope of
  (\log_{10}\sigma_y) against (\log_{10}\tau), using the last eight valid
  grid points, or all available points when fewer than eight remain. At least
  four points are required.

The long-time slope is assigned the following descriptive class:

| Log slope (s) | Stored description |
|---:|---|
| (s < -0.25) | improving with averaging |
| (-0.25 \le s \le 0.25) | stability floor / flicker-like |
| (0.25 < s < 0.75) | random-walk-like long-term drift |
| (s \ge 0.75) | strong drift / trend |

Run-level values in `metadata.json` and `allan_deviation_batch_summary.csv` are
medians across the selected pairs. In particular,
`MedianTauAtMinimum_s` is the median of the pairs' individual optimum times. It
is not obtained by first constructing a median Allan-deviation curve.

## Interpretation

A constant residue (c) cancels because

\[
(\bar y_{i+m}^{(m)}+c)-(\bar y_i^{(m)}+c)
=\bar y_{i+m}^{(m)}-\bar y_i^{(m)}.
\]

Consequently, a cumulative-mean plateau caused only by a nonzero residual does
not appear in Allan deviation. For a pure linear change (y(t)=y_0+dt), the
ideal contribution is

\[
\sigma_y^2(\tau)=\frac{d^2\tau^2}{2},
\qquad
\sigma_y(\tau)=\frac{|d|\tau}{\sqrt{2}},
\]

which has log-log deviation slope (+1). This relation can estimate a drift rate
only when linear drift is known to dominate the long-time curve.

An Allan-deviation tail is not exclusively drift. Correlated noise, random walk,
environmental changes, signal evolution, timing gaps, and finite-record
uncertainty can also flatten or raise it. The curves are not detrended, which
preserves real long-time changes but means the tail must be interpreted together
with the raw time trace and acquisition metadata.

The approximately one-second pre-averaging suppresses information below that
timescale. The standalone batch result should therefore be used for long-term
stability. The main pipeline's `allan_variance.csv` operates at the nominal raw
frame cadence and serves the shorter-time analysis.

## Output files

- `allan_deviation_long_term.csv`: complete tested curve for each selected pair.
- `allan_deviation_summary.csv`: pair-level minima, tails, slopes, and classes.
- `allan_deviation_long_term.png`: per-run log-log Allan-deviation curves.
- `metadata.json`: run-level method settings, timing details, and median results.
- `allan_deviation_batch_summary.csv`: one aggregate row per run.
- `allan_deviation_batch_visualization.png` and `.pdf`: cross-run minimum-to-tail
  stability trajectories generated by `plot_allan_batch_summary.py`.

## Reproduction

Run the batch calculation from the `post processing` directory:

```powershell
python .\allan_deviation_analysis.py "D:\Quantum Squeezing Project\DataFiles"
```

Generate the cross-run visualization from the repository root:

```powershell
python ".\post processing\plot_allan_batch_summary.py" `
  "D:\Quantum Squeezing Project\DataFiles\allan_deviation_batch_summary.csv" `
  --output ".\post processing\allan_deviation_batch_visualization"
```

## Method reference

The overlapping estimator follows the definition and terminology described in
W. J. Riley, *Handbook of Frequency Stability Analysis*, NIST Special Publication
1065, 2008: <https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication1065.pdf>.


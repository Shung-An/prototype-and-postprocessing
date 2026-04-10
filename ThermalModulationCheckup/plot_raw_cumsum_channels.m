% Plot moving-mean traces derived from cumulative sums and corresponding
% per-bin increments.
% This is meant as a sanity-check viewer before applying any modulation
% detection logic.

clear;
clc;

topN = 8;
pointDurationSec = 0.025;
modulationPeriodSec = 200;
lowFreqMaxHz = 0.02;
useFilePicker = true;

dataFilesDir = fullfile(pwd, 'DataFiles');
candidateFiles = {
    'pos_diff_cumsum_clean.mat'
    'pos_diffcumsum_clean.mat'
    };

matFile = '';
if useFilePicker
    startDir = pwd;
    if isfolder(dataFilesDir)
        startDir = dataFilesDir;
    end

    [fileName, filePath] = uigetfile(fullfile(startDir, '*.mat'), 'Select cumulative-sum MAT file');
    if isequal(fileName, 0)
        error('No MAT-file selected.');
    end
    matFile = fullfile(filePath, fileName);
else
    for k = 1:numel(candidateFiles)
        candidatePath = candidateFiles{k};
        if isfolder(dataFilesDir)
            candidatePath = fullfile(dataFilesDir, candidateFiles{k});
        end

        if isfile(candidatePath)
            matFile = candidatePath;
            break;
        end
    end
end

if isempty(matFile)
    error('Could not find pos_diff_cumsum_clean.mat or pos_diffcumsum_clean.mat.');
end

S = load(matFile);
if ~isfield(S, 'result')
    error('Expected the MAT-file to contain a variable named result.');
end

result = S.result;
rawBinValues = result.bin_values;
Xcumsum = localConvertCumsums(result.cumsums);
XmovingMean = localComputeMovingMean(Xcumsum);
labels = result.labels;

nTime = size(XmovingMean, 1);
nChannels = size(Xcumsum, 2);
t = localBuildTimeAxis(rawBinValues, nTime, pointDurationSec);
Xinc = [zeros(1, nChannels); diff(Xcumsum, 1, 1)];
dt = median(diff(t), 'omitnan');

if ~isfinite(dt) || dt <= 0
    error('Could not infer a valid time spacing from result.bin_values.');
end

fs = 1 / dt;
targetFreq = 1 / modulationPeriodSec;

if iscell(labels)
    labelList = string(labels(:));
elseif isstring(labels)
    labelList = labels(:);
elseif ischar(labels)
    labelList = string(cellstr(labels));
else
    labelList = strings(nChannels, 1);
end

if numel(labelList) ~= nChannels
    labelList = "Channel " + string(1:nChannels);
end

% Pick representative channels: either the ranked list if it exists,
% otherwise the channels with the largest increment variance.
if isfile('modulation_200s_channel_ranking.csv')
    try
        ranking = readtable('modulation_200s_channel_ranking.csv');
        rankedIdx = ranking.ChannelIndex(:);
        rankedIdx = rankedIdx(rankedIdx >= 1 & rankedIdx <= nChannels);
        displayIdx = rankedIdx(1:min(topN, numel(rankedIdx)));
    catch
        displayIdx = [];
    end
else
    displayIdx = [];
end

if isempty(displayIdx)
    incStd = std(Xinc, 0, 1, 'omitnan');
    [~, order] = sort(incStd, 'descend');
    displayIdx = order(1:min(topN, nChannels));
end

fprintf('Displaying %d channel(s):\n', numel(displayIdx));
disp(labelList(displayIdx));

figure('Color', 'w', 'Name', 'Moving mean and increments');
tiledlayout(numel(displayIdx), 2, 'Padding', 'compact', 'TileSpacing', 'compact');

for k = 1:numel(displayIdx)
    ch = displayIdx(k);

    nexttile;
    plot(t, XmovingMean(:, ch), 'k-', 'LineWidth', 1);
    xlabel('Time (s)');
    ylabel('Moving mean');
    title(sprintf('Moving mean: %s', char(labelList(ch))), 'Interpreter', 'none');
    grid on;

    nexttile;
    plot(t, Xinc(:, ch), 'b-', 'LineWidth', 0.8);
    xlabel('Time (s)');
    ylabel('Increment');
    title(sprintf('Increment: %s', char(labelList(ch))), 'Interpreter', 'none');
    grid on;
end

exportgraphics(gcf, 'raw_cumsum_channels.png', 'Resolution', 200);
fprintf('Saved moving-mean viewer figure to raw_cumsum_channels.png\n');

figure('Color', 'w', 'Name', 'Overview heatmaps');
tiledlayout(2, 1, 'Padding', 'compact', 'TileSpacing', 'compact');

nexttile;
imagesc(t, 1:nChannels, XmovingMean.');
axis xy;
xlabel('Time (s)');
ylabel('Channel');
title('Moving mean overview');
colorbar;

nexttile;
Xz = Xinc;
for ch = 1:nChannels
    s = std(Xz(:, ch), 0, 'omitnan');
    if ~isfinite(s) || s == 0
        s = 1;
    end
    Xz(:, ch) = Xz(:, ch) / s;
end
imagesc(t, 1:nChannels, Xz.');
axis xy;
xlabel('Time (s)');
ylabel('Channel');
title('Increment overview, z-scored by channel');
cb = colorbar;
cb.Label.String = 'z-score';

exportgraphics(gcf, 'raw_cumsum_overview.png', 'Resolution', 200);
fprintf('Saved overview figure to raw_cumsum_overview.png\n');

fftWindowHz = max(0.01, 8 / max(t(end) - t(1), eps));
fftSummary = localComputeFftSummary(XmovingMean, fs, targetFreq);
allChannelFftTable = localBuildFftPeakTable(fftSummary, labelList, targetFreq, lowFreqMaxHz);
sortedByTarget = sortrows(allChannelFftTable, 'TargetAmp', 'descend');
sortedByPeak = sortrows(allChannelFftTable, 'PeakAmp', 'descend');

disp('Top channels by 200 s FFT amplitude:');
disp(sortedByTarget(1:min(topN, height(sortedByTarget)), :));
disp('Top channels by strongest low-frequency peak:');
disp(sortedByPeak(1:min(topN, height(sortedByPeak)), :));

try
    writetable(sortedByPeak, 'all_channel_fft_peaks_200s.csv');
    fprintf('Saved FFT peak summary to all_channel_fft_peaks_200s.csv\n');
catch
end

figure('Color', 'w', 'Name', '200 s FFT view');
tiledlayout(numel(displayIdx), 2, 'Padding', 'compact', 'TileSpacing', 'compact');

for k = 1:numel(displayIdx)
    ch = displayIdx(k);
    freqs = fftSummary.freqs;
    amp = fftSummary.amplitude(:, ch);

    nexttile;
    plot(freqs, amp, 'k-', 'LineWidth', 1);
    hold on;
    xline(targetFreq, 'r--', 'LineWidth', 1);
    hold off;
    xlabel('Frequency (Hz)');
    ylabel('FFT amplitude');
    title(sprintf('FFT: %s', char(labelList(ch))), 'Interpreter', 'none');
    grid on;
    xlim([0, min(fs / 2, 0.05)]);

    nexttile;
    plot(freqs, amp, 'b-', 'LineWidth', 1);
    hold on;
    xline(targetFreq, 'r--', '200 s target', 'LineWidth', 1);
    hold off;
    xlabel('Frequency (Hz)');
    ylabel('FFT amplitude');
    title(sprintf('FFT near 1/200 Hz: %s', char(labelList(ch))), 'Interpreter', 'none');
    grid on;
    xlim([max(0, targetFreq - fftWindowHz), min(fs / 2, targetFreq + fftWindowHz)]);
end

exportgraphics(gcf, 'moving_mean_fft_200s.png', 'Resolution', 200);
fprintf('Saved FFT figure to moving_mean_fft_200s.png\n');

sortedIdx = sortedByPeak.ChannelIndex;
peakFreqImage = repmat(sortedByPeak.PeakFreq_Hz, 1, 2);
peakAmpImage = repmat(sortedByPeak.PeakAmp, 1, 2);

figure('Color', 'w', 'Name', 'All-channel FFT peak summary');
tiledlayout(2, 1, 'Padding', 'compact', 'TileSpacing', 'compact');

nexttile;
imagesc([1 2], 1:nChannels, peakFreqImage);
axis xy;
xlabel('Summary');
ylabel('Channel (sorted by peak amplitude)');
title(sprintf('Dominant low-frequency peak per channel (0 to %.3f Hz)', lowFreqMaxHz));
cb = colorbar;
cb.Label.String = 'Peak frequency (Hz)';
hold on;
for row = 1:nChannels
    text(1.5, row, sprintf(' %s', char(labelList(sortedIdx(row)))), ...
        'Color', 'w', 'Interpreter', 'none', 'FontSize', 8, ...
        'HorizontalAlignment', 'left', 'Clipping', 'on');
end
hold off;

nexttile;
imagesc([1 2], 1:nChannels, peakAmpImage);
axis xy;
xlabel('Summary');
ylabel('Channel (sorted by peak amplitude)');
title('Amplitude of dominant low-frequency peak');
cb = colorbar;
cb.Label.String = 'Peak FFT amplitude';
hold on;
for row = 1:nChannels
    text(1.5, row, sprintf(' %s', char(labelList(sortedIdx(row)))), ...
        'Color', 'w', 'Interpreter', 'none', 'FontSize', 8, ...
        'HorizontalAlignment', 'left', 'Clipping', 'on');
end
hold off;

exportgraphics(gcf, 'all_channel_fft_peak_summary.png', 'Resolution', 200);
fprintf('Saved all-channel FFT peak summary to all_channel_fft_peak_summary.png\n');

assignin('base', 'rawViewerTime', t);
assignin('base', 'rawViewerCumsum', Xcumsum);
assignin('base', 'rawViewerMovingMean', XmovingMean);
assignin('base', 'rawViewerIncrements', Xinc);
assignin('base', 'rawViewerChannels', displayIdx);
assignin('base', 'rawViewerFftFreqs', fftSummary.freqs);
assignin('base', 'rawViewerFftAmplitude', fftSummary.amplitude);
assignin('base', 'rawViewerFftTargetFreq', targetFreq);
assignin('base', 'rawViewerAllChannelFftTable', allChannelFftTable);

function Xmean = localComputeMovingMean(Xcumsum)
denom = (1:size(Xcumsum, 1))';
Xmean = Xcumsum ./ denom;
end

function fftSummary = localComputeFftSummary(X, fs, targetFreq)
nTime = size(X, 1);
nChannels = size(X, 2);
f = (0:nTime-1)' * fs / nTime;
posMask = f >= 0 & f <= fs / 2;
freqs = f(posMask);
amplitude = nan(numel(freqs), nChannels);
targetAmp = nan(nChannels, 1);

for ch = 1:nChannels
    x = X(:, ch);
    x = fillmissing(x, 'linear', 'EndValues', 'nearest');
    x = detrend(x, 1);
    x = x - mean(x, 'omitnan');

    Y = fft(x);
    amp = abs(Y) / nTime;
    amp = amp(posMask);
    amplitude(:, ch) = amp;

    [~, idx] = min(abs(freqs - targetFreq));
    targetAmp(ch) = amp(idx);
end

fftSummary = struct( ...
    'freqs', freqs, ...
    'amplitude', amplitude, ...
    'targetAmp', targetAmp);
end

function fftTable = localBuildFftPeakTable(fftSummary, labelList, targetFreq, lowFreqMaxHz)
freqs = fftSummary.freqs;
amplitude = fftSummary.amplitude;
nChannels = size(amplitude, 2);

lowMask = freqs > 0 & freqs <= lowFreqMaxHz;
targetIdx = find(abs(freqs - targetFreq) == min(abs(freqs - targetFreq)), 1, 'first');

peakFreq = nan(nChannels, 1);
peakAmp = nan(nChannels, 1);
targetAmp = nan(nChannels, 1);
peakToTargetRatio = nan(nChannels, 1);

for ch = 1:nChannels
    amp = amplitude(:, ch);
    targetAmp(ch) = amp(targetIdx);

    if any(lowMask)
        lowFreqs = freqs(lowMask);
        lowAmp = amp(lowMask);
        [peakAmp(ch), idx] = max(lowAmp);
        peakFreq(ch) = lowFreqs(idx);
    end

    if isfinite(targetAmp(ch)) && targetAmp(ch) > 0
        peakToTargetRatio(ch) = peakAmp(ch) / targetAmp(ch);
    end
end

fftTable = table( ...
    (1:nChannels)', ...
    labelList(:), ...
    peakFreq, ...
    peakAmp, ...
    targetAmp, ...
    peakToTargetRatio, ...
    'VariableNames', ...
    {'ChannelIndex', 'Label', 'PeakFreq_Hz', 'PeakAmp', 'TargetAmp', 'PeakToTargetRatio'});
end

function X = localConvertCumsums(rawCumsums)
numericValue = localExtractNumeric(rawCumsums);
if ~isempty(numericValue)
    X = double(numericValue);
    if isvector(X)
        X = X(:);
    end
    return;
end

if ~iscell(rawCumsums)
    error('result.cumsums must be numeric or a cell array.');
end

if isvector(rawCumsums)
    nChannels = numel(rawCumsums);
    lengths = zeros(nChannels, 1);
    values = cell(nChannels, 1);
    for k = 1:nChannels
        values{k} = localExtractNumeric(rawCumsums{k});
        if isempty(values{k})
            error('Could not extract numeric data from result.cumsums{%d}.', k);
        end
        values{k} = double(values{k}(:));
        lengths(k) = numel(values{k});
    end

    nTime = max(lengths);
    X = nan(nTime, nChannels);
    for k = 1:nChannels
        X(1:numel(values{k}), k) = values{k};
    end
    return;
end

error('Unsupported cumsums layout.');
end

function value = localExtractNumeric(x)
value = [];

if isnumeric(x) || islogical(x)
    value = x;
    return;
end

if iscell(x)
    if isempty(x)
        return;
    end

    if isscalar(x)
        value = localExtractNumeric(x{1});
        return;
    end

    extracted = cell(size(x));
    ok = true(size(x));
    for k = 1:numel(x)
        extracted{k} = localExtractNumeric(x{k});
        ok(k) = ~isempty(extracted{k}) && isscalar(extracted{k});
    end

    if all(ok(:))
        value = cellfun(@double, extracted);
    end
    return;
end

if isstruct(x)
    fieldNames = fieldnames(x);
    for k = 1:numel(fieldNames)
        candidate = localExtractNumeric(x.(fieldNames{k}));
        if ~isempty(candidate)
            value = candidate;
            return;
        end
    end
end
end

function t = localBuildTimeAxis(rawBinValues, nTime, pointDurationSec)
t = [];

if isnumeric(rawBinValues)
    candidate = double(rawBinValues(:));
elseif iscell(rawBinValues) && all(cellfun(@(c) isnumeric(c) && isscalar(c), rawBinValues(:)))
    candidate = cellfun(@double, rawBinValues(:));
else
    candidate = [];
end

if numel(candidate) == nTime
    diffs = diff(candidate);
    if all(isfinite(candidate)) && all(isfinite(diffs)) && any(diffs > 0)
        dtCandidate = median(diffs(diffs > 0));
        if isfinite(dtCandidate) && dtCandidate > 0 && dtCandidate <= 1
            t = candidate;
        end
    end
end

if isempty(t)
    t = (0:nTime-1)' * pointDurationSec;
end
end

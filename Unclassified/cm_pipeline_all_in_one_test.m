function cm_pipeline_all_in_one_test
% ==========================================================
% Quantum Squeezing: CM + simplified processing for cm.bin only
% This version works even if only cm.bin is present.
% ==========================================================

%% ---------- Config ----------
runFolder = 'C:\Quantum Squeezing\Labuser_test\GageStreamThruGPU-Optimize';
disp(['Using run folder: ' runFolder]);

bin_mm         = 0.1;                  % bin size (still defined for consistency)
scale_factor   = (0.24^2) / (32768^2); % convert raw ADC to V^2
mm_to_ps       = 6.6;                  % conversion (for labeling only)
frame_dt_s     = 0.025;                % 25 ms per frame
CF_max         = 1;                    % fallback Conversion Factor
scale_to_urad2 = @(v) (v ./ CF_max) * 1; % Convert V² → µrad²

%% ---------- Anti-diagonal pairs ----------
pairs = [
    1 1 8 8; 1 2 7 8; 2 2 8 8; 3 3 8 8; 4 4 8 8; 5 5 8 8; 6 6 8 8; 7 7 8 8;
    ];
pairLabels = arrayfun(@(k)sprintf('(%d,%d)-(%d,%d)',pairs(k,:)),1:size(pairs,1),'uni',0);

%% ---------- Locate cm.bin ----------
fCM = fullfile(runFolder,'cm.bin');
assert(isfile(fCM), 'cm.bin not found in %s', runFolder);

%% ---------- Load CM ----------
cm = readCM64(fCM);
cm = cm * scale_factor;
[N, nCh] = size(cm);
fprintf('Loaded cm.bin with %d frames × %d channels\n', N, nCh);
assert(nCh==64, 'Expected 64 channels.');

%% ---------- Create synthetic time and position ----------
tCM_s = (0:N-1)' * frame_dt_s;     % seconds
posOnCM = ones(N,1) * 25.058;      % constant position (no pos file)
%% ---------- Show ALL pixels (cumulative curves + heatmaps) ----------
% Convert to µrad² units at the channel level, then build cumulative averages
cm_urad2 = scale_to_urad2(cm);            % N×64
cum_all  = cumsum(cm_urad2, 1) ./ (1:N)'; % N×64 cumulative average per pixel

% ---------- (A) Overlay: all 64 cumulative curves ----------
f1 = figure('Color','w','Name','All pixels cumulative (overlay)');
hold on; grid on; box on;
for k = 1:64
    loglog(tCM_s, abs(cum_all(:,k)), 'LineWidth', 0.7);
end
xlabel('Time (s, log scale)');
ylabel('|Cumulative Amplitude (µrad²)|');
title('All 64 pixels — cumulative averages (overlay)');
set(gca,'XScale','log','YScale','log');
exportgraphics(f1, fullfile(runFolder,'all_pixels_cumsum_overlay.png'), 'Resolution', 300);
close(f1);

% ---------- (B) Small multiples: 8×8 cumulative curves ----------
f2 = figure('Color','w','Name','All pixels cumulative (8x8)');
tiledlayout(8,8,'Padding','compact','TileSpacing','compact');
for r = 1:8
    for c = 1:8
        k = sub2ind([8 8], r, c);
        nexttile;
        loglog(tCM_s, abs(cum_all(:,k)), 'LineWidth', 0.8);
        set(gca,'XScale','log','YScale','log');
        xticks([]); yticks([]);
        title(sprintf('(%d,%d)', r, c), 'FontSize', 8);
    end
end
exportgraphics(f2, fullfile(runFolder,'all_pixels_cumsum_small_multiples.png'), 'Resolution', 300);
close(f2);

% ---------- (C) 8×8 heatmaps (final cumulative, mean|.|, RMS) ----------
finalCum = reshape(abs(cum_all(end,:)), 8, 8);                % final cumulative magnitude
meanAbs  = reshape(mean(abs(cm_urad2),1,'omitnan'), 8, 8);    % mean absolute value
rmsVal   = reshape(sqrt(mean(cm_urad2.^2,1,'omitnan')), 8, 8);% RMS

f3 = figure('Color','w','Name','Pixel heatmaps (8x8)');
tiledlayout(1,3,'Padding','compact','TileSpacing','compact');

nexttile; imagesc(finalCum); axis image; colorbar;
title('Final |cumulative| (µrad²)'); set(gca,'YDir','normal');

nexttile; imagesc(meanAbs); axis image; colorbar;
title('Mean |value| (µrad²)'); set(gca,'YDir','normal');

nexttile; imagesc(rmsVal); axis image; colorbar;
title('RMS (µrad²)'); set(gca,'YDir','normal');

colormap('parula');
exportgraphics(f3, fullfile(runFolder,'pixel_heatmaps_8x8.png'), 'Resolution', 300);
close(f3);

%% ---------- Bin positions ----------
posBin = round(posOnCM / bin_mm) * bin_mm;
[binVals, ~, grp] = unique(posBin);
nBins = numel(binVals);
fprintf('Using constant position %.3f mm -> %d bin(s)\n', binVals, nBins);

%% ---------- Compute cumulative sums ----------
idx = @(r,c) sub2ind([8 8], r, c);
cumsums = cell(size(pairs,1),1);
for p = 1:numel(cumsums), cumsums{p} = cell(nBins,1); end
counts = zeros(nBins,1);

for b = 1:nBins
    idxFrames = find(grp == b);
    counts(b) = numel(idxFrames);
    if counts(b) == 0, continue; end
    M = cm(idxFrames,:);
    for p = 1:size(pairs,1)
        r1=pairs(p,1); c1=pairs(p,2);
        r2=pairs(p,3); c2=pairs(p,4);
        a = M(:, idx(r1,c1));
        b2= M(:, idx(r2,c2));
        d  = a - b2;
        v  = cumsum(d) ./ (1:numel(d))';     % cumulative average over time
        cumsums{p}{b} = scale_to_urad2(v);

    end
end

%% ---------- Save result + Averages ----------
result = struct();
result.bin_step_mm  = bin_mm;
result.bin_values   = binVals;
result.counts       = counts;
result.mm_to_ps     = mm_to_ps;
result.pairs        = pairs;
result.labels       = {pairLabels{:}};
result.cumsums      = cumsums;
result.CF_max       = CF_max;

% ---- (1) Per-pair, per-bin mean of raw differences (NOT cumulative) ----
pairMeanDiff = nan(size(pairs,1), nBins);
pairMeanAbsDiff = nan(size(pairs,1), nBins);

for b = 1:nBins
    idxFrames = find(grp == b);
    if isempty(idxFrames), continue; end
    M = cm(idxFrames,:);
    for p = 1:size(pairs,1)
        r1=pairs(p,1); c1=pairs(p,2);
        r2=pairs(p,3); c2=pairs(p,4);
        a  = M(:, idx(r1,c1));
        b2 = M(:, idx(r2,c2));
        d  = scale_to_urad2(a - b2);
        pairMeanDiff(p,b)    = mean(d,'omitnan');
        pairMeanAbsDiff(p,b) = mean(abs(d),'omitnan');
    end
end

% ---- (2) Per-pair mean cumulative curve across bins (element-wise) ----
% Align all bin curves to shortest available length for that pair.
pairMeanCum = cell(size(pairs,1),1);
pairKmin    = zeros(size(pairs,1),1);

for p = 1:size(pairs,1)
    % find shortest length across bins for this pair
    lengths = cellfun(@(x) iff(isempty(x), 0, numel(x)), cumsums{p});
    kmin_p  = min(lengths(lengths>0));
    pairKmin(p) = kmin_p;
    if isempty(kmin_p) || kmin_p==0
        pairMeanCum{p} = [];
        continue;
    end
    stack = nan(kmin_p, nBins);
    for b = 1:nBins
        v = cumsums{p}{b};
        if ~isempty(v) && numel(v) >= kmin_p
            stack(:,b) = v(1:kmin_p);
        end
    end
    pairMeanCum{p} = mean(stack, 2, 'omitnan');   % mean across bins
end

% ---- (3) Grand-mean cumulative curve across all pairs (and bins) ----
% Align by the minimum pairKmin across those with data.
validK = pairKmin(pairKmin>0);
if ~isempty(validK)
    kmin_global = min(validK);
    grandStack = nan(kmin_global, size(pairs,1));
    for p = 1:size(pairs,1)
        if ~isempty(pairMeanCum{p}) && numel(pairMeanCum{p}) >= kmin_global
            grandStack(:,p) = pairMeanCum{p}(1:kmin_global);
        end
    end
    grandMeanCum = mean(grandStack, 2, 'omitnan');
else
    kmin_global = [];
    grandMeanCum = [];
end

% Attach to result
result.mean_diff_per_pair_bin     = pairMeanDiff;      % (pairs × bins)
result.mean_absdiff_per_pair_bin  = pairMeanAbsDiff;   % (pairs × bins)
result.mean_cumsum_per_pair       = pairMeanCum;       % cell of vectors
result.kmin_per_pair              = pairKmin(:);       % shortest length used
result.kmin_global                = iff(isempty(validK), 0, kmin_global);
result.grand_mean_cumsum          = grandMeanCum;      % vector (kmin_global×1)

save(fullfile(runFolder,'pos_diff_cumsum_only_cm.mat'), 'result','-v7.3');
fprintf('Saved result struct (with averages).\n');

%% ---------- Quick plot (single-bin + averages) ----------
% Original single-bin diagnostic, plus overlays of per-pair mean and grand mean
kmin_single = min(result.counts(result.counts>0));
if isempty(kmin_single) || kmin_single < 1
    warning('No valid data for plotting.');
    return;
end

f = figure('Color','w'); hold on;

% original: plot single-bin curves (use first nonempty bin)
firstBin = find(result.counts>0, 1, 'first');
for p = 1:numel(pairLabels)
    v = result.cumsums{p}{firstBin};
    if ~isempty(v)
        kk = min(numel(v), kmin_single);
        loglog((1:kk)*frame_dt_s, abs(v(1:kk)), ...
            'DisplayName', ['Bin1 ' pairLabels{p}]);
    end
end

% overlay per-pair mean cumulative curves
for p = 1:size(pairs,1)
    vbar = result.mean_cumsum_per_pair{p};
    if ~isempty(vbar)
        tt = (1:numel(vbar))*frame_dt_s;
        loglog(tt, abs(vbar), 'LineWidth', 1.5, ...
            'DisplayName', ['MeanBin ' pairLabels{p}]);
    end
end

% overlay grand-mean cumulative curve (bold)
if ~isempty(result.grand_mean_cumsum)
    ttg = (1:numel(result.grand_mean_cumsum))*frame_dt_s;
    loglog(ttg, abs(result.grand_mean_cumsum), 'LineWidth', 2.5, ...
        'DisplayName', 'Grand mean (all pairs & bins)');
end

xlabel('Time (s, log scale)');
ylabel('|Cumulative Amplitude (µrad²)|, log scale');
title('Log-Log Cumulative Sum: single bin vs. mean across bins/pairs');
legend('Location','bestoutside');
grid on; box on;
set(gca, 'XScale', 'log', 'YScale', 'log');
exportgraphics(f, fullfile(runFolder, 'cumsum_only_cm_loglog_with_means.png'), 'Resolution', 300);
close(f);

disp('All done — processed cm.bin with averages (plot saved).');

% ---------- tiny utility ----------
    function y = iff(cond,a,b)
        if cond, y = a; else, y = b; end
    end


end

% ================== Helpers ==================
function cm = readCM64(filename)
fid = fopen(filename,'rb');
assert(fid~=-1,'Cannot open %s',filename);
raw = fread(fid,'double'); fclose(fid);
assert(mod(numel(raw),64)==0,'Data length not multiple of 64 doubles.');
cm = reshape(raw,64,[]).';
end

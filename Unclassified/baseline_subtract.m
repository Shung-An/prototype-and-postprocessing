function baseline_subtract(baselineFolder, targetFolder)
% ==========================================================
% Baseline subtraction for Quantum Squeezing cumulative sums
%
% Loads "pos_diff_cumsum_allpairs_converted.mat" from baselineFolder
% and targetFolder, aligns positions, computes per-bin cumulative
% averages, interpolates baseline onto target positions, and subtracts.
%
% Output: baseline_subtracted.mat saved in targetFolder
% Fields:
%   subtracted.bin_values   -> position bins (mm, from target)
%   subtracted.diffVals     -> [nBins x nPairs] µrad^2 baseline-subtracted
%   subtracted.labels       -> pair labels
%   subtracted.targetAvg    -> raw target averages
%   subtracted.baseInterp   -> interpolated baseline averages
% ==========================================================

%% --- Load datasets ---
base = load(fullfile(baselineFolder, 'pos_diff_cumsum_allpairs_converted.mat'));
targ = load(fullfile(targetFolder,  'pos_diff_cumsum_allpairs_converted.mat'));

base = base.result;
targ = targ.result;

%% --- Prepare ---
pos_base = base.bin_values(:);
pos_targ = targ.bin_values(:);
nPairs   = numel(targ.cumsums);
nBinsT   = numel(pos_targ);

diffVals   = nan(nBinsT, nPairs);
targetAvg  = nan(nBinsT, nPairs);
baseInterp = nan(nBinsT, nPairs);

%% --- Overlap region only ---
minPos = max(min(pos_base), min(pos_targ));
maxPos = min(max(pos_base), max(pos_targ));
inOverlap = (pos_targ >= minPos & pos_targ <= maxPos);

%% --- Compute averages per pair ---
for p = 1:nPairs
    % --- baseline averages per bin ---
    baseBinAvg = nan(size(pos_base));
    for b = 1:numel(pos_base)
        vB = base.cumsums{p}{b};
        if ~isempty(vB)
            baseBinAvg(b) = mean(vB); % cumulative average over frames
        end
    end

    % --- target averages per bin ---
    for b = 1:nBinsT
        vT = targ.cumsums{p}{b};
        if ~isempty(vT)
            targetAvg(b,p) = mean(vT);
        end
    end

    % --- interpolate baseline onto target positions (within overlap) ---
    good = ~isnan(baseBinAvg);
    if sum(good) >= 2
        baseInterp(inOverlap,p) = interp1(pos_base(good), baseBinAvg(good), ...
                                          pos_targ(inOverlap), 'linear','extrap');
    end

    % --- subtract baseline from target ---
    diffVals(inOverlap,p) = targetAvg(inOverlap,p) - baseInterp(inOverlap,p);
end

%% --- Save results ---
subtracted = struct();
subtracted.bin_values = pos_targ;
subtracted.diffVals   = diffVals;
subtracted.labels     = targ.labels;
subtracted.targetAvg  = targetAvg;
subtracted.baseInterp = baseInterp;
subtracted.overlap    = [minPos, maxPos];

save(fullfile(targetFolder,'baseline_subtracted.mat'),'subtracted');

fprintf('✅ Baseline subtraction complete.\n');
fprintf('   Overlap region: %.3f – %.3f mm (%d bins)\n', ...
        minPos, maxPos, sum(inOverlap));
fprintf('   Output saved to %s\n', fullfile(targetFolder,'baseline_subtracted.mat'));
end

function baseline_subtract_and_plot_root()
% ==========================================================
% Baseline subtraction + contour plotting (with root)
% ==========================================================

root = 'Z:\Quantum Squeezing Project\DataFiles';

%% --- Select baseline folder ---
baselineFolder = uigetdir(root,'Select baseline run folder');
if baselineFolder==0, disp('❌ No baseline selected.'); return; end
fBase = fullfile(baselineFolder,'pos_diff_cumsum_allpairs_converted.mat');
assert(isfile(fBase),'Baseline file not found: %s', fBase);
baseData = load(fBase); base = baseData.result;

%% --- Select target folder ---
targetFolder = uigetdir(root,'Select target run folder');
if targetFolder==0, disp('❌ No target selected.'); return; end
fTarg = fullfile(targetFolder,'pos_diff_cumsum_allpairs_converted.mat');
assert(isfile(fTarg),'Target file not found: %s', fTarg);
targData = load(fTarg); targ = targData.result;

%% --- Prepare ---
pos_base = base.bin_values(:);
pos_targ = targ.bin_values(:);
nPairs   = numel(targ.cumsums);
nBinsT   = numel(pos_targ);

diffVals   = nan(nBinsT, nPairs);
targetAvg  = nan(nBinsT, nPairs);
baseInterp = nan(nBinsT, nPairs);

% --- Overlap region ---
minPos = max(min(pos_base), min(pos_targ));
maxPos = min(max(pos_base), max(pos_targ));
inOverlap = (pos_targ >= minPos & pos_targ <= maxPos);

%% --- Compute averages + subtract ---
for p = 1:nPairs
    % Baseline averages
    baseBinAvg = nan(size(pos_base));
    for b = 1:numel(pos_base)
        vB = base.cumsums{p}{b};
        if ~isempty(vB)
            baseBinAvg(b) = mean(vB);
        end
    end

    % Target averages
    for b = 1:nBinsT
        vT = targ.cumsums{p}{b};
        if ~isempty(vT)
            targetAvg(b,p) = mean(vT);
        end
    end

    % Interpolate baseline → target bins
    good = ~isnan(baseBinAvg);
    if sum(good) >= 2
        baseInterp(inOverlap,p) = interp1(pos_base(good), baseBinAvg(good), ...
                                          pos_targ(inOverlap), 'linear','extrap');
    end

    % Subtract
    diffVals(inOverlap,p) = targetAvg(inOverlap,p) - baseInterp(inOverlap,p);
end

%% --- Save result in target folder ---
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

%% --- Plot contour ---
ampsPlot = diffVals;
ampsPlot(isnan(ampsPlot)) = 0; % replace NaN for plotting

[X,Y] = meshgrid(1:nPairs, pos_targ);

figure('Color','w','Position',[100,100,1400,600]);
contourf(X,Y,ampsPlot,30,'LineColor','none');
colormap jet;
c = colorbar;
c.Label.String = 'Baseline-subtracted amplitude (\mu rad^2)';

xlabel('Pair index');
ylabel('Delay stage position (mm)');
title('Baseline-subtracted contour');

% Optional: use pair labels if not too many
if nPairs <= 20
    xticks(1:nPairs);
    xticklabels(targ.labels);
    xtickangle(45);
else
    xticks(1:5:nPairs);
end

end

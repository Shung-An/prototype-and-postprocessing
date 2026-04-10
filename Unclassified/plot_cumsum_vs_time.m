function plot_cumsum_vs_time
% Plot cumsum amplitudes at the common frame index kmin vs delay time
% Reads pos_diff_cumsum_allpairs.mat produced by cm_pipeline_all_in_one

%% --- Pick the run folder & load results ---
root = 'Z:\Quantum Squeezing Project\DataFiles';
runFolder = uigetdir(root, 'Select Run Folder');
if runFolder == 0, return; end
inMat = fullfile(runFolder, 'pos_diff_cumsum_allpairs.mat');
S = load(inMat); result = S.result;

% Convert bin positions (mm) to time (ps)
mm_to_ps = result.mm_to_ps;
t_ps = result.bin_values * mm_to_ps;   % [nBins x 1] picoseconds

%% --- Find the fewest frames across all bins ---
counts = result.counts(:);
kmin   = min(counts(counts > 0));
if isempty(kmin) || kmin < 1
    error('No non-empty bins found.');
end
fprintf('Using frame index kmin = %d (fewest frames across bins)\n', kmin);

%% --- Collect cumsum amplitude at kmin for each pair ---
nBins = numel(result.bin_values);
P     = numel(result.labels);
amps  = nan(nBins,P);

for p = 1:P
    for b = 1:nBins
        v = result.cumsums{p}{b};
        if numel(v) >= kmin
            amps(b,p) = v(kmin);
        end
    end
end

% --- Sort by delay time for nicer plotting ---
[ts, ord] = sort(t_ps);
amps      = amps(ord,:);
pos_sorted= result.bin_values(ord);

%% --- Plot ---
f = figure('Color','w'); hold on;
markers = {'o','s','^','v','d','>','<','p','h'}; % extendable

for p = 1:P
    plot(ts, amps(:,p), markers{1+mod(p-1,numel(markers))}, ...
        'LineStyle','none','LineWidth',1.5,'MarkerSize',6, ...
        'DisplayName', result.labels{p});
end

% --- Limit to ~10 ticks ---
nTicksMax = 10;
tickIdx   = round(linspace(1, numel(ts), min(nTicksMax, numel(ts))));
set(gca, 'XTick', ts(tickIdx), ...
         'XTickLabel', arrayfun(@(t) sprintf('%.3f', t), ts(tickIdx), 'UniformOutput', false), ...
         'XTickLabelRotation', 45);

xlabel('Delay time (ps)');
ylabel(sprintf('Cumsum amplitude at frame %d (V^2)', kmin));
title(sprintf('Cumsum at common frame index k = %d vs delay time', kmin));
legend('Location','bestoutside');
grid on; box on;

% --- Save figure ---
outPng = fullfile(runFolder, sprintf('cumsum_at_kmin_%d_vs_delaytime_multi.png', kmin));
exportgraphics(f, outPng, 'Resolution', 300);
fprintf('Saved plot: %s\n', outPng);
end

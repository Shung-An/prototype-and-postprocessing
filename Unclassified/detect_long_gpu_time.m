% ==========================================================
% Script: detect_long_gpu_and_transfer_time.m
% Purpose: Find indices in profile.txt with unusually long
%          GPU Process Time and Transfer+Process Time
% ==========================================================

% --- Config ---
filename = 'C:\Quantum Squeezing\Labuser_test\GageStreamThruGPU-Optimize\profile.txt';  % input log file

% --- Read and parse lines ---
lines = readlines(filename);
gpu_times = nan(numel(lines),1);
transfer_times = nan(numel(lines),1);

pattern_gpu = "GPU Process Time:\s*([\d\.]+)";
pattern_transfer = "Transfer and process Time:\s*([\d\.]+)";

for i = 1:numel(lines)
    tok_gpu = regexp(lines(i), pattern_gpu, 'tokens', 'once');
    tok_trans = regexp(lines(i), pattern_transfer, 'tokens', 'once');
    if ~isempty(tok_gpu)
        gpu_times(i) = str2double(tok_gpu{1});
    end
    if ~isempty(tok_trans)
        transfer_times(i) = str2double(tok_trans{1});
    end
end

gpu_times = gpu_times(~isnan(gpu_times));
transfer_times = transfer_times(~isnan(transfer_times));

% ==========================================================
% Robust statistics (MAD method)
% ==========================================================
med_gpu = median(gpu_times);
mad_gpu = mad(gpu_times, 1);
threshold_gpu = med_gpu + 6 * mad_gpu;

med_trans = median(transfer_times);
mad_trans = mad(transfer_times, 1);
threshold_trans = med_trans + 6 * mad_trans;

% --- Find anomalies ---
bad_gpu_idx = find(gpu_times > threshold_gpu);
bad_trans_idx = find(transfer_times > threshold_trans);

fprintf('--- GPU Process Time ---\n');
fprintf('Median: %.2f ms | MAD: %.2f | Threshold: %.2f ms\n', med_gpu, mad_gpu, threshold_gpu);
fprintf('Detected %d anomalies.\n\n', numel(bad_gpu_idx));

fprintf('--- Transfer & Process Time ---\n');
fprintf('Median: %.2f ms | MAD: %.2f | Threshold: %.2f ms\n', med_trans, mad_trans, threshold_trans);
fprintf('Detected %d anomalies.\n\n', numel(bad_trans_idx));

% ==========================================================
% Visualization
% ==========================================================
figure('Color','w','Name','GPU & Transfer Time Analysis');
t = tiledlayout(1,2,'TileSpacing','compact','Padding','compact');

% ===== Left tile: Timeline =====
ax1 = nexttile;
plot(ax1, gpu_times, 'b.-', 'DisplayName','GPU Time');
hold(ax1, 'on');
plot(ax1, transfer_times, 'Color',[0.2 0.7 0.2], 'LineStyle','-.', 'DisplayName','Transfer+Process Time');
yline(ax1, threshold_gpu, 'r--', 'DisplayName','GPU Threshold');
yline(ax1, threshold_trans, 'm--', 'DisplayName','Transfer Threshold');

xlabel(ax1, 'Iteration Index');
ylabel(ax1, 'Processing Time (ms)');
title(ax1, 'Timeline of GPU & Transfer Times');
grid(ax1, 'on');
legend(ax1, 'show', 'Location', 'northwest');

% Zoom scale control
full_range = false;  % toggle to true to include spikes
if ~full_range
    y_max = prctile([gpu_times; transfer_times], 99) * 1.1;
    ylim(ax1, [0 y_max]);
end

% Annotate anomalies
if ~isempty(bad_gpu_idx)
    for i = 1:numel(bad_gpu_idx)
        text(ax1, bad_gpu_idx(i), gpu_times(bad_gpu_idx(i)), sprintf('%.0f', gpu_times(bad_gpu_idx(i))), ...
            'VerticalAlignment','bottom', 'HorizontalAlignment','right', ...
            'Color','b', 'FontWeight','bold');
    end
end
if ~isempty(bad_trans_idx)
    for i = 1:numel(bad_trans_idx)
        text(ax1, bad_trans_idx(i), transfer_times(bad_trans_idx(i)), sprintf('%.0f', transfer_times(bad_trans_idx(i))), ...
            'VerticalAlignment','bottom', 'HorizontalAlignment','left', ...
            'Color',[0.2 0.6 0.2], 'FontWeight','bold');
    end
end

% ===== Right tile: Horizontal Histogram =====
ax2 = nexttile;
h1 = histogram(ax2, gpu_times, 'BinWidth', 0.5, ...
    'FaceColor',[0.2 0.4 0.8], 'EdgeColor','none', 'FaceAlpha',0.6, ...
    'Orientation','horizontal', 'DisplayName','GPU Time');
hold(ax2, 'on');
h2 = histogram(ax2, transfer_times, 'BinWidth', 0.5, ...
    'FaceColor',[0.3 0.7 0.3], 'EdgeColor','none', 'FaceAlpha',0.5, ...
    'Orientation','horizontal', 'DisplayName','Transfer+Process Time');

yline(ax2, threshold_gpu, 'r--', 'LineWidth',1.2, 'DisplayName','GPU Threshold');
yline(ax2, threshold_trans, 'm--', 'LineWidth',1.2, 'DisplayName','Transfer Threshold');

xlabel(ax2, 'Count');
ylabel(ax2, 'Processing Time (ms)');
title(ax2, 'Distribution of GPU & Transfer Times');
grid(ax2, 'on');
legend(ax2, 'show', 'Location', 'northwest');

% --- Match Y limits between plots ---
ylims = [0, max([gpu_times; transfer_times])*1.05];
ylim(ax1, ylims);
ylim(ax2, ylims);
linkaxes([ax1 ax2], 'y');

% --- Adjust histogram X limit for neatness ---
xlim(ax2, [0, max([h1.Values h2.Values])*1.2]);


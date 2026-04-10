function inspect_variance_gating(target_folder)
% =========================================================================
% INSPECT VARIANCE GATING
% Visualizes how the "Dead Frames" (Sharp Spike) are removed.
% - Plots Histogram BEFORE and AFTER gating.
% - Plots Time Series BEFORE and AFTER gating.
% - Calculates the Variance of the cleaned signal.
% =========================================================================

%% 1. Select Folder
if nargin < 1
    startPath = 'D:\Quantum Squeezing Project\DataFiles';
    if ~isfolder(startPath), startPath = pwd; end
    runFolder = uigetdir(startPath, 'Select Data Folder');
else
    runFolder = target_folder;
end

fCM = fullfile(runFolder,'cm.bin');
assert(isfile(fCM), 'cm.bin not found.');

%% 2. Load Data
fprintf('Loading data...\n');
fid = fopen(fCM,'rb'); raw = fread(fid,'double'); fclose(fid);
cm = reshape(raw, 64, []).';
N_total = size(cm, 1);

% Filter Hard Saturation first (Standard step)
cm(cm(:,1) > 1e-6, :) = [];

%% 3. Calculate Frame Energy (RMS)
fprintf('Calculating Frame Energies...\n');
frame_rms = std(cm, 0, 2); % Standard deviation of each frame (across 64 ch)

%% 4. Determine Cutoff (IsoData Algorithm)
T = mean(frame_rms); 
for iter = 1:50
    g1 = frame_rms(frame_rms < T);
    g2 = frame_rms(frame_rms >= T);
    if isempty(g1) || isempty(g2), break; end
    T_new = (mean(g1) + mean(g2)) / 2;
    if abs(T - T_new) < 1e-12, break; end
    T = T_new;
end
rms_cutoff = T;

% Identify Dead Frames
is_dead = frame_rms < rms_cutoff;
cm_clean = cm(~is_dead, :);
frame_rms_clean = frame_rms(~is_dead);

%% 5. Calculate Final Signal Variance (Shot Noise)
% Using pair (1,1) and (8,8) as a reference
chA = sub2ind([8 8], 1, 1);
chB = sub2ind([8 8], 8, 8);
diff_signal = cm_clean(:, chA) - cm_clean(:, chB);
final_variance = var(diff_signal);

fprintf('\n=== GATING RESULTS ===\n');
fprintf('Total Frames:      %d\n', numel(frame_rms));
fprintf('Dead Frames (Cut): %d (%.1f%%)\n', sum(is_dead), sum(is_dead)/numel(frame_rms)*100);
fprintf('Kept Frames:       %d\n', sum(~is_dead));
fprintf('Cutoff RMS:        %.2e\n', rms_cutoff);
fprintf('Clean Signal Var:  %.2e V^2 (Shot Noise)\n', final_variance);
fprintf('======================\n');

%% 6. PLOT: Comparison
f = figure('Name', 'Variance Gating Inspection', 'Color', 'w', 'Position', [50 50 1200 800]);

% --- Plot 1: Histogram BEFORE ---
subplot(2, 2, 1);
histogram(frame_rms, 100, 'FaceColor', [.6 .6 .6]); hold on;
xline(rms_cutoff, 'r--', 'Cutoff', 'LineWidth', 2);
title('1. Raw Distribution (Before)');
subtitle('Look for the "Spike" on the left');
xlabel('Frame RMS'); ylabel('Count'); grid on;

% --- Plot 2: Histogram AFTER ---
subplot(2, 2, 2);
histogram(frame_rms_clean, 100, 'FaceColor', [0 0.4470 0.7410]);
title('2. Gated Distribution (After)');
subtitle('Should be a clean Gaussian (Signal only)');
xlabel('Frame RMS'); ylabel('Count'); grid on;
xlim([min(frame_rms) max(frame_rms)]); % Keep scale same for comparison

% --- Plot 3: Timeline BEFORE ---
subplot(2, 2, 3);
plot(frame_rms, 'Color', [.6 .6 .6]); hold on;
yline(rms_cutoff, 'r--', 'LineWidth', 2);
title('3. Timeline (Raw)');
subtitle('Low points are detector dropouts');
xlabel('Frame Index'); ylabel('RMS'); grid on;
ylim([0 max(frame_rms)*1.1]);

% --- Plot 4: Timeline AFTER ---
subplot(2, 2, 4);
plot(find(~is_dead), frame_rms_clean, '.', 'Color', [0 0.4470 0.7410]);
title('4. Timeline (Kept Frames)');
subtitle('Consistent energy level');
xlabel('Original Frame Index'); ylabel('RMS'); grid on;
ylim([0 max(frame_rms)*1.1]);

exportgraphics(f, fullfile(runFolder, 'variance_gating_comparison.png'));
fprintf('Comparison plot saved to: variance_gating_comparison.png\n');

end
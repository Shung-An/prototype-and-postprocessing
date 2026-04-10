function cm_pipeline_all_in_one(target_folder)
% ==========================================================
% Quantum Squeezing Pipeline
% - Filter 1: Variance Gating (Active)
% - Filter 2: PCA (Removed)
% - Filter 3: Channel Health (Active)
% ==========================================================
set(0, 'DefaultFigureVisible', 'off');
%% ---------- Config ----------
if nargin < 1 || isempty(target_folder)
    fprintf('No target folder provided. Opening folder selector...\n');
    startPath = 'D:\Quantum Squeezing Project\DataFiles';
    if ~isfolder(startPath), startPath = pwd; end
    runFolder = uigetdir(startPath, 'Select the Data Run Folder');
    if runFolder == 0, error('Cancelled.'); end
else
    runFolder = target_folder;
end

% Physics Config
bin_mm         = 0.1;                  
scale_factor   = (0.24^2) / (32768^2); 
mm_to_ps       = 6.6;                  
max_xticks     = 10;                   
frame_dt_s     = 0.025;                
rel_threshold  = 0.20;  

%% ---------- Anti-diagonal pairs ----------
pairs = [
    1 1 8 8; 1 2 7 8; 1 3 6 8; 1 4 5 8; 1 5 4 8; 1 6 3 8; 1 7 2 8;
    2 2 8 8; 2 3 7 8; 2 4 6 8; 2 5 5 8; 2 6 4 8; 2 7 3 8;
    3 3 8 8; 3 4 7 8; 3 5 6 8; 3 6 5 8; 3 7 4 8;
    4 4 8 8; 4 5 7 8; 4 6 6 8; 4 7 5 8;
    5 5 8 8; 5 6 7 8; 5 7 6 8;
    6 6 8 8; 6 7 7 8;
    7 7 8 8;
    2 1 8 7; 3 1 8 6; 4 1 8 5; 5 1 8 4; 6 1 8 3; 7 1 8 2;
    3 2 8 7; 4 2 8 6; 5 2 8 5; 6 2 8 4; 7 2 8 3;
    4 3 8 7; 5 3 8 6; 6 3 8 5; 7 3 8 4;
    5 4 8 7; 6 4 8 6; 7 4 8 5;
    6 5 8 7; 7 5 8 6;
    7 6 8 7
    ];

selectedLabels = {
    '(2,2)-(8,8)','(2,3)-(7,8)','(2,4)-(6,8)', ...
    '(3,2)-(8,7)','(3,3)-(7,7)','(3,4)-(6,7)', ...
    '(4,2)-(8,6)','(4,3)-(7,6)','(4,4)-(6,6)', ...
    '(1,7)-(2,8)','(7,6)-(8,7)'
    };

pairLabels = cell(size(pairs,1),1);
for k = 1:size(pairs,1), pairLabels{k} = sprintf('(%d,%d)-(%d,%d)', pairs(k,:)); end

%% ---------- Load Data & Metadata ----------
fCM = fullfile(runFolder,'cm.bin');
fProfile = fullfile(runFolder,'profile.txt');
fPos = find_first(runFolder, ["delay_stage_positions.log","delay_stage_positions.csv"]);
fSens = fullfile(runFolder,'sensitivity.log');

assert(isfile(fCM), 'cm.bin not found.');

cm = readCM64(fCM);
cm = cm * scale_factor;
[N, ~] = size(cm);
tCM = read_times_from_profile(fProfile, N);

L = min(N, numel(tCM));
cm = cm(1:L,:); tCM = tCM(1:L); N = L;
tCM_s = seconds(tCM - tCM(1));

% --- Extract Physics Metadata ---
meta = readSensitivityLog(runFolder);
if isnan(meta.ConversionFactor)
    warning('Conversion Factor not found. Using default 1e4.');
    CF_max = 1e4;
else
    CF_max = meta.ConversionFactor;
end
scale_to_urad2 = @(v) (v ./ CF_max) * 1e12; 

% --- Load Positions & Range ---
if fPos == ""
    posOnCM = ones(N,1) * 25.058;
    meta.ScanRange = 0; meta.ScanMin = 25.058; meta.ScanMax = 25.058;
else
    [posTime, posVal] = read_positions_series(fPos);
    if isdatetime(posTime), t_pos_dur = timeofday(posTime); else, t_pos_dur = posTime; end
    if isdatetime(tCM),     t_cm_dur  = timeofday(tCM(1));  else, t_cm_dur  = tCM(1);  end
    
    dt = seconds(t_pos_dur - t_cm_dur);
    valid_mask = isfinite(dt) & isfinite(posVal);
    dt = dt(valid_mask); posVal = posVal(valid_mask);
    
    if isempty(dt)
        posOnCM = ones(N,1) * posVal(1);
    else
        [pu, ia] = unique(dt); pv = posVal(ia);
        if numel(pu) < 2, posOnCM = ones(N,1) * pv(1);
        else, posOnCM = interp1(pu, pv, tCM_s, 'linear', 'extrap'); end
    end
    meta.ScanRange = max(posOnCM) - min(posOnCM);
    meta.ScanMin = min(posOnCM);
    meta.ScanMax = max(posOnCM);
end

fprintf('\n================ METADATA ================\n');
fprintf('  Power (P1/P2):      %.2f / %.2f mW\n', meta.P1_mW, meta.P2_mW);
fprintf('  Scan Range:         %.3f mm\n', meta.ScanRange);
fprintf('  Conversion Factor:  %.2e\n', CF_max);
fprintf('  Shot Noise (Log):   %.2f urad^2/rtHz\n', meta.ShotNoiseResult);
fprintf('==========================================\n');

%% ---------- Basic Cleanup (FIXED) ----------
% FIX: Ensure tCM_s and posOnCM are filtered using the SAME MASK as cm.
% Previously, cm rows were deleted but tCM_s was just truncated at the end.
dirty_mask = cm(:,1) > 1e-6;
if any(dirty_mask)
    fprintf('Removing %d frames due to CH1 saturation (>1e-6).\n', sum(dirty_mask));
    cm(dirty_mask, :) = []; 
    tCM_s(dirty_mask) = [];
    tCM(dirty_mask) = []; % Keep datetime aligned
    posOnCM(dirty_mask) = [];
    N = size(cm,1);
end

% Ch(1,1) Histogram (Diagnostic Only)
ch11 = sub2ind([8 8],1,1);
xV2 = cm(:, ch11);
ampU = scale_to_urad2(abs(xV2));
if ~isempty(ampU)
    fV = figure('Color','w','Position',[120 120 1000 650]); 
    histogram(xV2, 80); grid on; title('Ch(1,1) Amplitude (Raw)');
    exportgraphics(fV, fullfile(runFolder,'hist_ch11_amplitude_V2.png')); close(fV);
end

%% ---------- FILTER 0: DROPPED WINDOWS & BASIC CLEANUP ----------
fprintf('\n--- DROPPED WINDOW GATING ---\n');
fDropped = fullfile(runFolder, 'dropped_window.log');
if isfile(fDropped)
    txt_dropped = fileread(fDropped);
    % Extract the start and end times from "Between: START - END"
    drop_tokens = regexp(txt_dropped, 'Between:\s*(\d{2}:\d{2}:\d{2}\.\d+)\s*-\s*(\d{2}:\d{2}:\d{2}\.\d+)', 'tokens');
    
    if ~isempty(drop_tokens)
        is_dropped = false(size(tCM));
        tCM_tod = timeofday(tCM); % Use timeofday to strip arbitrary dates
        
        for i = 1:numel(drop_tokens)
            try
                % Parse times
                d_start = timeofday(datetime(drop_tokens{i}{1}, 'InputFormat', 'HH:mm:ss.SSS'));
                d_end   = timeofday(datetime(drop_tokens{i}{2}, 'InputFormat', 'HH:mm:ss.SSS'));
                
                % Add to dropped mask
                is_dropped = is_dropped | (tCM_tod >= d_start & tCM_tod <= d_end);
            catch
                warning('Could not parse dropped window: %s - %s', drop_tokens{i}{1}, drop_tokens{i}{2});
            end
        end
        
        n_dropped = sum(is_dropped);
        if n_dropped > 0
            fprintf('Removing %d frames (%.1f%%) inside dropped windows.\n', n_dropped, (n_dropped/N)*100);
            cm(is_dropped, :)   = [];
            tCM_s(is_dropped)   = [];
            tCM(is_dropped)     = [];
            posOnCM(is_dropped) = [];
            N = size(cm, 1);
        else
            fprintf('No frames matched the dropped windows.\n');
        end
    else
        fprintf('No valid dropped window formats found in log.\n');
    end
else
    fprintf('dropped_window.log not found. Skipping.\n');
end

fprintf('\n--- BASIC SATURATION CLEANUP ---\n');
dirty_mask = cm(:,1) > 1e-6;
if any(dirty_mask)
    fprintf('Removing %d frames due to CH1 saturation (>1e-6).\n', sum(dirty_mask));
    cm(dirty_mask, :)   = []; 
    tCM_s(dirty_mask)   = [];
    tCM(dirty_mask)     = []; % Keep datetime aligned
    posOnCM(dirty_mask) = [];
    N = size(cm,1);
end

% Ch(1,1) Histogram (Diagnostic Only)
ch11 = sub2ind([8 8],1,1);
xV2 = cm(:, ch11);
ampU = scale_to_urad2(abs(xV2));
if ~isempty(ampU)
    fV = figure('Color','w','Position',[120 120 1000 650]); 
    histogram(xV2, 80); grid on; title('Ch(1,1) Amplitude (Raw)');
    exportgraphics(fV, fullfile(runFolder,'hist_ch11_amplitude_V2.png')); close(fV);
end

%% ---------- FILTER 1: VARIANCE GATING (ACTIVE) ----------
fprintf('\n--- VARIANCE GATING (Dead Frame Removal) ---\n');
frame_rms = std(cm, 0, 2); 
T = mean(frame_rms); 

for iter = 1:50
    g1 = frame_rms(frame_rms < T); g2 = frame_rms(frame_rms >= T);
    if isempty(g1) || isempty(g2), break; end
    T_new = (mean(g1) + mean(g2)) / 2;
    if abs(T - T_new) < 1e-12, break; end
    T = T_new;
end
rms_cutoff = T;

% Visual Check
f_var = figure('Name','Frame Variance Check','Color','w','Position',[50 50 1000 500]);
histogram(frame_rms, 100, 'FaceColor', 'b'); hold on;
xline(rms_cutoff, 'r--', 'Cutoff (Auto)', 'LineWidth', 2);
grid on; xlabel('Frame RMS'); ylabel('Count');
title('Distribution of Frame Energy (Auto-Threshold)');
exportgraphics(f_var, fullfile(runFolder, 'variance_gating_check.png')); close(f_var);

is_dead_frame = frame_rms < rms_cutoff;
n_dead = sum(is_dead_frame);

if n_dead > 0
    fprintf('Rejecting %d frames (%.1f%%) based on Low Variance.\n', n_dead, (n_dead/N)*100);
    % [CRITICAL STEP] The data 'cm' is OVERWRITTEN here. Bad frames are deleted.
    cm = cm(~is_dead_frame, :); 
    tCM_s = tCM_s(~is_dead_frame); 
    tCM = tCM(~is_dead_frame); % Ensure datetime stays aligned
    posOnCM = posOnCM(~is_dead_frame);
    N = size(cm,1);
else
    fprintf('No low-variance frames found.\n');
end

%% ---------- FILTER 2: PCA STRIPE GATING (REMOVED) ----------
% This section has been removed per request.

%% ---------- FILTER 3: CHANNEL HEALTH CHECK (ACTIVE) ----------
channel_kurt = kurtosis(cm);
bad_chs = find(channel_kurt > 5.0);
valid_pair_mask = true(size(pairs,1), 1);
idx_ch = @(r,c) sub2ind([8 8], r, c);

if ~isempty(bad_chs)
    fprintf('\n[WARN] Found %d bad channels (Kurtosis > 5).\n', numel(bad_chs));
    for i = 1:size(pairs,1)
        if ismember(idx_ch(pairs(i,1),pairs(i,2)), bad_chs) || ismember(idx_ch(pairs(i,3),pairs(i,4)), bad_chs)
            valid_pair_mask(i) = false;
        end
    end
    fprintf('Removing %d pairs containing bad channels.\n', sum(~valid_pair_mask));
    pairs = pairs(valid_pair_mask, :);
    pairLabels = pairLabels(valid_pair_mask);
end

%% ---------- Position Binning & Report ----------
posBin = round(posOnCM / bin_mm) * bin_mm;
[binVals, ~, grp] = unique(posBin);
counts = accumarray(grp, 1);
min_count = round(rel_threshold * mean(counts(counts>0)));

keep_bins = counts >= min_count;
binVals = binVals(keep_bins); counts = counts(keep_bins);
valid_indices = find(keep_bins);
nBins = numel(binVals);

fprintf('\nProcessing %d valid position bins...\n', nBins);
binVals = binVals(:); counts = counts(:); 
T_counts = table(binVals, counts, 'VariableNames', {'Position_mm', 'FrameCount'});
try writetable(T_counts, fullfile(runFolder, 'frames_per_position.csv')); catch; end

f_counts = figure('Color','w','Position',[100 100 900 500]);
bar(binVals, counts, 'FaceColor', [0.2 0.4 0.7]);
yline(min_count, '--r', 'Threshold'); grid on;
title('Available Frames per Position (Filtered)');
exportgraphics(f_counts, fullfile(runFolder, 'frames_per_position_hist.png')); close(f_counts);

%% ---------- Prepare per-bin cumulative sums ----------
idx_lin = @(r,c) sub2ind([8 8], r, c);
cumsums = cell(size(pairs,1), 1);
for p = 1:numel(cumsums), cumsums{p} = cell(nBins,1); end

for b = 1:nBins
    orig_idx = valid_indices(b);
    % cm here is ALREADY filtered by variance gating
    M = cm(grp == orig_idx, :); 
    for p = 1:size(pairs,1)
        i1 = idx_lin(pairs(p,1), pairs(p,2));
        i2 = idx_lin(pairs(p,3), pairs(p,4));
        cumsums{p}{b} = scale_to_urad2(cumsum(M(:,i1) - M(:,i2)));
    end
end

%% ---------- Save & Plot Results (K-Min) ----------
% 1. Save Raw Data
result = struct('bin_values', binVals, 'cumsums', {cumsums}, ...
                'labels', {pairLabels}, 'metadata', meta);
save(fullfile(runFolder,'pos_diff_cumsum_clean.mat'), 'result','-v7.3');

if isempty(counts), error('No data left after filtering.'); end

% 2. Calculate Final Amplitudes for ALL pairs
kmin = min(counts);
nPairs = size(pairs,1);
fprintf('Calculating results at k = %d frames for all %d pairs...\n', kmin, nPairs);

amps = nan(nBins, nPairs);
for p = 1:nPairs
    for b = 1:nBins
        if ~isempty(cumsums{p}{b})
            % Use average at kmin (or end if count is slightly off)
            current_len = numel(cumsums{p}{b});
            idx_use = min(current_len, kmin);
            if idx_use > 0
                amps(b,p) = cumsums{p}{b}(idx_use) / idx_use; 
            end
        end
    end
end

% 3. Sort Data by Time Delay
t_ps = binVals * mm_to_ps;
[ts, ord] = sort(t_ps);
amps = amps(ord,:);

% 4. Export Table to CSV (Crucial for analyzing all pairs)
% Sanitize variable names for CSV (remove brackets/dashes)
csvHeaders = strrep(strrep(strrep(pairLabels, '(', ''), ')', ''), '-', '_');
T_results = array2table([ts, amps], 'VariableNames', [{'Delay_ps'}; csvHeaders]);
writetable(T_results, fullfile(runFolder, 'final_amplitudes_all_pairs.csv'));
fprintf('Saved CSV data for all pairs.\n');

% 5. PLOT 1: ALL PAIRS (The Master Plot)
f_all = figure('Name', 'All Pairs Result', 'Color', 'w', 'Position', [50 50 1600 900]);
hold on;
% Generate distinct colors for all pairs
colors = turbo(nPairs); 
for p = 1:nPairs
    plot(ts, amps(:,p), '-o', 'Color', colors(p,:), ...
        'DisplayName', pairLabels{p}, 'LineWidth', 1, 'MarkerSize', 4);
end
grid on; xlabel('Delay (ps)'); ylabel('Amplitude (\mu rad^2)');
title({sprintf('ALL Pairs Result at k=%d', kmin), ...
       sprintf('Power: %.2fmW | Range: %.1fmm | ShotNoise: %.1f', ...
       meta.P1_mW+meta.P2_mW, meta.ScanRange, meta.ShotNoiseResult)});

% Legend Logic: If >20 pairs, legend obscures the data. 
% We save the .fig so you can click lines to identify them.
if nPairs <= 20
    legend('Location','bestoutside', 'Interpreter', 'none');
else
    text(min(ts), max(amps(:)), '  Legend suppressed (Too many pairs). Open .fig to inspect.', ...
        'VerticalAlignment', 'top', 'BackgroundColor', 'w', 'EdgeColor', 'k');
end

% Save both PNG and FIG (FIG allows interactive inspection of specific lines)
exportgraphics(f_all, fullfile(runFolder, 'final_result_ALL_PAIRS.png'));
savefig(f_all, fullfile(runFolder, 'final_result_ALL_PAIRS.fig'));
close(f_all);

% 6. PLOT 2: SELECTED PAIRS (The Summary Plot)
% This provides a cleaner view of the specific pairs of interest defined at the top
f_sel = figure('Name', 'Selected Pairs Summary', 'Color','w'); hold on;
keep_lbl = find(ismember(pairLabels, selectedLabels));
if isempty(keep_lbl), keep_lbl = 1:min(10, nPairs); end % Default to first 10 if no match
for i = 1:numel(keep_lbl)
    p = keep_lbl(i);
    plot(ts, amps(:,p), 'o-', 'DisplayName', pairLabels{p}, 'LineWidth', 1.5);
end
grid on; xlabel('Delay (ps)'); ylabel('Amplitude (\mu rad^2)');
title('Selected Pairs Summary');
legend('Location','bestoutside', 'Interpreter', 'none');
exportgraphics(f_sel, fullfile(runFolder, 'final_clean_result.png')); 
close(f_sel);


%% ---------- Grouped Line Plots (Log-Log Convergence) ----------
% REPLACED CONTOUR PLOTS WITH LOG-LOG LINE PLOTS
% X-Axis: Integration Time (Log Scale)
% Y-Axis: Absolute Amplitude (Log Scale)
groups = { 1:7, 8:13, 14:18, 19:22, 23:25, 26:27, 28, 29:34, 35:39, 40:43, 44:46, 47:48, 49 };

if nBins > 1
    fprintf('Generating log-log convergence plots...\n');
    for g = 1:numel(groups)
        idxList = groups{g};
        idxList = idxList(idxList <= size(pairs,1)); 
        if isempty(idxList), continue; end
        
        nPlots = numel(idxList);
        nRows = ceil(sqrt(nPlots)); 
        nCols = ceil(nPlots/nRows);
        
        fBig = figure('Visible','off','Position',[100 100 1600 900]);
        t = tiledlayout(nRows,nCols,'TileSpacing','compact', 'Padding', 'compact');
        
        for k = 1:nPlots
            p = idxList(k);
            frames_per_bin = min(cellfun(@numel, result.cumsums{p}));
            
            % Prepare Data Matrix: [Rows=Bins, Cols=Frames]
            ampMat = nan(nBins, frames_per_bin);
            for b = 1:nBins
                v = result.cumsums{p}{b};
                if ~isempty(v)
                    len = min(numel(v), frames_per_bin);
                    % Calculate running average
                    cumavg = v(1:len) ./ (1:len)'; 
                    ampMat(b,1:len) = cumavg;
                end
            end
            
            % --- PLOTTING ---
            nexttile;
            time_axis = (1:frames_per_bin) * frame_dt_s; % Start at 1 to avoid log(0)
            
            % Set Color Cycle for Bins (Jet Colormap)
            set(gca, 'ColorOrder', jet(nBins)); 
            
            % LOG-LOG PLOT
            % Note: We use abs() because log scale cannot handle negative numbers.
            % Transpose ampMat so lines represent bins.
            loglog(time_axis, abs(ampMat'), 'LineWidth', 1);
            
            title(pairLabels{p}, 'Interpreter', 'none', 'FontSize', 10);
            grid on; 
            
            % Only label axes on edges to save space
            if k > (nRows-1)*nCols, xlabel('Time (s)'); end
            if mod(k-1, nCols) == 0, ylabel('|\mu rad^2|'); end
            
            % Optional: Add reference slope (1/sqrt(t) or 1/t)
            % This helps you see if it's averaging down like white noise.
            % (Uncomment below to enable)
            % hold on; 
            % ref_line = (time_axis.^(-0.5)) * (nanmedian(abs(ampMat(:,1)))/10);
            % loglog(time_axis, ref_line, 'k--', 'LineWidth', 1);
        end
        
        % Add colorbar for Position
        cb = colorbar;
        cb.Layout.Tile = 'east';
        cb.Label.String = 'Position (mm)';
        caxis([min(binVals) max(binVals)]);
        colormap(cb, jet);
        
        title(t, sprintf('Log-Log Convergence (Group %d)', g));
        
        exportgraphics(fBig, fullfile(runFolder, sprintf('loglog_convergence_group%d.png',g)), 'Resolution',150);
        close(fBig);
    end
end


%% ---------- MOVIE GENERATION: SIGNAL EVOLUTION ----------
% This section generates an MP4 showing the signal emerging from noise
% as the number of integrated frames (k) increases.

fprintf('\n--- GENERATING SIGNAL EVOLUTION MOVIE ---\n');

% 1. Config
movieFile = fullfile(runFolder, 'signal_emergence.mp4');
v = VideoWriter(movieFile, 'MPEG-4');
v.FrameRate = 15; % Playback speed (frames per second)
open(v);

% 2. Setup Frame Steps (Smart Downsampling)
% We don't need to plot k=1, k=2... if we have 10,000 frames.
% We create ~400 frames for the movie to keep it under 30 seconds.
k_max_common = min(counts); % The limit where all bins have data
n_movie_frames = 400; 
frame_steps = unique(round(linspace(1, k_max_common, n_movie_frames)));

% 3. Prepare the Figure
f_mov = figure('Visible','off', 'Color','w', 'Position', [100 100 1200 700]);
% Create plot handles for selected pairs only (to keep it clean)
keep_lbl = find(ismember(pairLabels, selectedLabels));
if isempty(keep_lbl), keep_lbl = 1:min(5, size(pairs,1)); end % Fallback

% Initialize plot lines with NaN data
hLines = gobjects(numel(keep_lbl), 1);
colors_mov = lines(numel(keep_lbl));
ax = axes('Parent', f_mov);
hold(ax, 'on'); grid(ax, 'on');
for i = 1:numel(keep_lbl)
    hLines(i) = plot(ax, ts, nan(size(ts)), 'o-', ...
        'Color', colors_mov(i,:), ...
        'LineWidth', 1.5, ...
        'DisplayName', pairLabels{keep_lbl(i)});
end
xlabel(ax, 'Delay (ps)'); ylabel(ax, 'Amplitude (\mu rad^2)');
legend(ax, 'Location', 'bestoutside', 'Interpreter', 'none');

% 4. Determine Y-Limits (Optional: Fix visuals to avoid jumping)
% We calculate the final range to keep the axis steady, or let it auto-scale.
% For "seeing the signal emerge", Fixed Limits are usually better so the 
% signal "grows" rather than the axis shrinking.
% Let's use the final frame's amplitude to set a sensible range.
final_amps = amps(:, keep_lbl);
y_max_limit = max(final_amps(:)) * 1.5;
y_min_limit = min(final_amps(:)) * 1.2;
% If noise is huge at k=1, we might clip it, but that's okay.
ylim(ax, [y_min_limit, y_max_limit]); 

fprintf('Rendering %d frames for video...\n', length(frame_steps));

% 5. The Rendering Loop
for i = 1:length(frame_steps)
    k = frame_steps(i);
    
    % Update data for each selected pair
    for j = 1:numel(keep_lbl)
        p = keep_lbl(j);
        current_amps = nan(nBins, 1);
        
        for b = 1:nBins
            % Get the cumulative sum for this pair/bin
            % result.cumsums{p}{b} exists from previous section
            if numel(result.cumsums{p}{b}) >= k
                % MATH: Average = CumulativeSum(k) / k
                val_at_k = result.cumsums{p}{b}(k); 
                current_amps(b) = val_at_k / k;
            end
        end
        
        % Sort by time (ts is sorted binVals * mm_to_ps)
        % We must map the current_amps (ordered by bin index) to sorted 'ts'
        % 'ord' was calculated in the "Sort Data by Time Delay" section
        sorted_amps = current_amps(ord);
        
        % Update the specific line handle
        set(hLines(j), 'YData', sorted_amps);
    end
    
    title(ax, sprintf('Integration: %d Frames (%.2fs)', k, k * frame_dt_s));
    
    % Capture and write
    drawnow limitrate;
    frame = getframe(f_mov);
    writeVideo(v, frame);
    
    if mod(i, 50) == 0, fprintf('  Rendered %d / %d\n', i, length(frame_steps)); end
end

close(v);
close(f_mov);
fprintf('Movie saved to: %s\n', movieFile);
%% ---------- Variation & FFT Plots ----------
fprintf('Generating Variation & FFT plots...\n');
[~, bestBinIdx] = max(counts);
f_var = figure('Color','w', 'Position', [100 100 1200 700]); hold on;
f_fft = figure('Color','w', 'Position', [100 100 1200 700]); hold on;

for i = 1:numel(keep_lbl)
    p = keep_lbl(i);
    v = result.cumsums{p}{bestBinIdx}; % Filtered/Cleaned Cumsums
    if numel(v) > 2
        % v is CumSum. To get variations, we need the raw values (diff)
        rawVals = [v(1); diff(v)];
        
        % Variation
        figure(f_var); plot((1:numel(rawVals)-1)*frame_dt_s, diff(rawVals), 'DisplayName', pairLabels{p});
        
        % FFT
        figure(f_fft); 
        L = numel(rawVals); Y = fft(rawVals); P2 = abs(Y/L); P1 = P2(1:floor(L/2)+1); P1(2:end-1) = 2*P1(2:end-1);
        f = (1/frame_dt_s)*(0:(L/2))/L;
        plot(f, P1, 'DisplayName', pairLabels{p});
    end
end
figure(f_var); legend; title('Frame Variation (Cleaned)'); exportgraphics(f_var, fullfile(runFolder, 'variation_vs_time.png')); close(f_var);
figure(f_fft); set(gca,'YScale','log'); legend; title('FFT Spectrum (Cleaned)'); exportgraphics(f_fft, fullfile(runFolder, 'fft_spectrum.png')); close(f_fft);

%% ---------- Log–Log Evaluation ----------
idx_ch = @(r,c) sub2ind([8 8], r, c);
f_ll = figure('Color','w','Position',[100 100 900 650]); hold on;
time_tail = tCM_s - tCM_s(1); n_tail = numel(time_tail);

for i = 1:numel(keep_lbl)
    p = keep_lbl(i);
    i1 = idx_ch(pairs(p,1),pairs(p,2));
    i2 = idx_ch(pairs(p,3),pairs(p,4));
    
    % Recalculate mean from cleaned data
    runMean = cumsum(cm(:,i1) - cm(:,i2)) ./ (1:n_tail)';
    plot(time_tail, abs(scale_to_urad2(runMean)), 'DisplayName', pairLabels{p});
end
set(gca,'XScale','log','YScale','log'); grid on; legend;
title('Log-Log Evaluation (Cleaned)');
exportgraphics(f_ll, fullfile(runFolder,'loglog_eval.png')); close(f_ll);

%% ---------- UPDATE METADATA JSON ----------
fprintf('\n--- UPDATING METADATA.JSON ---\n');
jsonFile = fullfile(runFolder, 'metadata.json');
json_struct = struct();
if isfile(jsonFile)
    try
        fid = fopen(jsonFile, 'r'); rawJSON = fread(fid, '*char')'; fclose(fid);
        json_struct = jsondecode(rawJSON);
    catch, warning('Could not parse metadata.json. Creating new one.'); end
else, fprintf('metadata.json not found. Creating new one.\n'); end

json_struct.PhysicsData.Power_mW_1 = meta.P1_mW;
json_struct.PhysicsData.Power_mW_2 = meta.P2_mW;
json_struct.PhysicsData.Sensitivity_V_photon = meta.Sensitivity;
json_struct.PhysicsData.ShotNoise1_V = meta.ShotNoise1_V;
json_struct.PhysicsData.ShotNoise2_V = meta.ShotNoise2_V;
json_struct.PhysicsData.SignalLevel_V2_rtHz = meta.SignalLevel;
json_struct.PhysicsData.ConversionFactor_V2_rad2 = meta.ConversionFactor;
json_struct.PhysicsData.ShotNoiseResult_urad2_rtHz = meta.ShotNoiseResult;
json_struct.PhysicsData.ScanRange_mm = meta.ScanRange;
json_struct.PhysicsData.ScanMin_mm = meta.ScanMin;
json_struct.PhysicsData.ScanMax_mm = meta.ScanMax;

try
    encodedJSON = jsonencode(json_struct, 'PrettyPrint', true);
    fid = fopen(jsonFile, 'w'); fwrite(fid, encodedJSON); fclose(fid);
    fprintf('Successfully updated %s\n', jsonFile);
catch ME, warning('Failed to write JSON: %s', ME.message); end

try extra_analysis(cm, frame_dt_s, runFolder, CF_max, pairs, pairLabels); catch; end
fprintf('Pipeline Completed Successfully.\n');
end

% ================== Helpers ==================
function meta = readSensitivityLog(runFolder)
    meta = struct();
    meta.P1_mW = NaN; meta.P2_mW = NaN;
    meta.Sensitivity = NaN; meta.ShotNoise1_V = NaN; meta.ShotNoise2_V = NaN;
    meta.SignalLevel = NaN; meta.ConversionFactor = NaN; meta.ShotNoiseResult = NaN;
    
    f = fullfile(runFolder, 'sensitivity.log');
    if ~isfile(f), return; end
    
    txt = fileread(f);
    extractVal = @(pat) str2double(regexp(txt, pat, 'tokens', 'once'));
    
    meta.P1_mW = extractVal('P1\s*=\s*([\d\.]+)\s*mW');
    meta.P2_mW = extractVal('P2\s*=\s*([\d\.]+)\s*mW');
    meta.Sensitivity = extractVal('Sensitivity\s*=\s*([\d\.E\+\-]+)');
    meta.ShotNoise1_V = extractVal('Shot Noise1\s*=\s*([\d\.E\+\-]+)');
    meta.ShotNoise2_V = extractVal('Shot Noise2\s*=\s*([\d\.E\+\-]+)');
    meta.SignalLevel = extractVal('Signal Level\s*=\s*([\d\.E\+\-]+)');
    meta.ConversionFactor = extractVal('Conversion Factor\s*=\s*([\d\.E\+\-]+)');
    meta.ShotNoiseResult = extractVal('Shot Noise Result\s*=\s*([\d\.E\+\-]+)');
end

function cm = readCM64(f), fid=fopen(f,'rb'); r=fread(fid,'double'); fclose(fid); cm=reshape(r,64,[]).'; end
function t = read_times_from_profile(f,N), txt=fileread(f); 
    tok=regexp(txt,'start timestamp:\s*(\S+)','tokens');
    if isempty(tok), t=datetime(0,0,0)+milliseconds(0:N-1); else, 
    try t=datetime([tok{:}],'InputFormat','HH:mm:ss.SSS'); catch, t=datetime([tok{:}],'InputFormat','HH:mm:ss.SSSSSS'); end, end, t=t(1:min(numel(t),N)); end
function [pt, pv] = read_positions_series(f), T=readtable(f); pt=T{:,1}; pv=T{:,end}; 
    if isstring(pt), pt=datetime(pt,'InputFormat','HH:mm:ss.SSS'); end; end
function f = find_first(d, n), f=""; for i=1:numel(n), c=fullfile(d,n(i)); if isfile(c), f=c; return; end; end; end
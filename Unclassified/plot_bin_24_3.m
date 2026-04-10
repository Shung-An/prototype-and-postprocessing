function plot_loglog_bin_24_3_all_pairs(target_folder)
% ==========================================================
% Log-Log Convergence Plot for Position 24.3 mm
% - Includes ALL pair combinations.
% - Applies Variance & Kurtosis Filters.
% - Plots on Log-Log scales (Time vs Amplitude).
% ==========================================================

%% 1. Select Folder
if nargin < 1
    target_folder = uigetdir(pwd, 'Select Data Folder');
    if target_folder == 0, return; end
end

fprintf('Loading data from: %s\n', target_folder);

% Hardcoded Target
TARGET_POS_MM = 24.3; 
TOLERANCE_MM  = 0.05; 

% Physics Config
scale_factor = (0.24^2) / (32768^2); 
mm_to_ps     = 6.6;   
frame_dt_s   = 0.025; 

% --- FULL PAIR LIST (From original pipeline) ---
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

pairLabels = cell(size(pairs,1),1);
for k = 1:size(pairs,1), pairLabels{k} = sprintf('(%d,%d)-(%d,%d)', pairs(k,:)); end

%% 2. Load and Sync
fCM = fullfile(target_folder,'cm.bin');
fProfile = fullfile(target_folder,'profile.txt');
fPos = find_first(target_folder, ["delay_stage_positions.log","delay_stage_positions.csv"]);
fSens = fullfile(target_folder,'sensitivity.log');

if ~isfile(fCM), error('cm.bin not found'); end

% Load CM
fid=fopen(fCM,'rb'); r=fread(fid,'double'); fclose(fid);
cm = reshape(r,64,[]).' * scale_factor;
[N, ~] = size(cm);

% Load Time
txt=fileread(fProfile); 
tok=regexp(txt,'start timestamp:\s*(\S+)','tokens');
if isempty(tok), tCM=datetime(0,0,0)+milliseconds(0:N-1); else
try tCM=datetime([tok{:}],'InputFormat','HH:mm:ss.SSS'); catch, tCM=datetime([tok{:}],'InputFormat','HH:mm:ss.SSSSSS'); end, end
tCM = tCM(1:min(numel(tCM),N));
tCM_s = seconds(tCM - tCM(1));

% Load Positions
if fPos == ""
    posOnCM = ones(N,1) * 25.058; 
    fprintf('Warning: No position log found. Assuming static.\n');
else
    T=readtable(fPos); pt=T{:,1}; pv=T{:,end};
    if isstring(pt), pt=datetime(pt,'InputFormat','HH:mm:ss.SSS'); end
    if isdatetime(pt), t_pos = timeofday(pt); else, t_pos = pt; end
    if isdatetime(tCM), t_cm = timeofday(tCM(1)); else, t_cm = tCM(1); end
    
    dt = seconds(t_pos - t_cm);
    
    % Fix NaNs
    valid_mask = isfinite(dt) & isfinite(pv);
    dt = dt(valid_mask); pv = pv(valid_mask);
    
    if isempty(dt)
        posOnCM = ones(N,1) * pv(1);
    else
        [pu, ia] = unique(dt); pv = pv(ia);
        if numel(pu) < 2, posOnCM = ones(N,1) * pv(1);
        else, posOnCM = interp1(pu, pv, tCM_s, 'linear', 'extrap'); end
    end
end

% Physics Metadata
meta_txt = fileread(fSens);
tok_cf = regexp(meta_txt, 'Conversion Factor\s*=\s*([\d\.E\+\-]+)', 'tokens', 'once');
if isempty(tok_cf), CF = 1e4; else, CF = str2double(tok_cf); end
scale_to_urad2 = @(v) (v ./ CF) * 1e12; 

%% 3. Apply Filters
% A. Variance Gating
rms = std(cm, 0, 2);
cutoff = mean(rms) * 0.5; 
cm(rms < cutoff, :) = [];
posOnCM(rms < cutoff) = [];
fprintf('After Variance Filter: %d frames left.\n', size(cm,1));

% B. Kurtosis Check
k = kurtosis(cm);
bad_chs = find(k > 5.0);
valid_pair_mask = true(size(pairs,1), 1);
idx_ch = @(r,c) sub2ind([8 8], r, c);

for i = 1:size(pairs,1)
    chA = idx_ch(pairs(i,1), pairs(i,2));
    chB = idx_ch(pairs(i,3), pairs(i,4));
    if ismember(chA, bad_chs) || ismember(chB, bad_chs)
        valid_pair_mask(i) = false;
    end
end
pairs = pairs(valid_pair_mask, :);
pairLabels = pairLabels(valid_pair_mask);
fprintf('After Kurtosis Check: Keeping %d clean pairs.\n', size(pairs,1));

%% 4. Extract Data at 24.3 mm
target_mask = abs(posOnCM - TARGET_POS_MM) < TOLERANCE_MM;
M = cm(target_mask, :);
nFrames = size(M, 1);

fprintf('Found %d frames at %.3f mm.\n', nFrames, TARGET_POS_MM);
if nFrames < 10, warning('Not enough data to plot.'); return; end

%% 5. Generate Log-Log Plot
f = figure('Name', 'Log-Log Convergence', 'Color','w', 'Position', [50 50 1200 800]); 
idx_lin = @(r,c) sub2ind([8 8], r, c);
time_axis = (1:nFrames) * frame_dt_s;

% Use a colormap to distinguish the many lines
colors = jet(size(pairs,1));
hold on;

for p = 1:size(pairs,1)
    i1 = idx_lin(pairs(p,1), pairs(p,2));
    i2 = idx_lin(pairs(p,3), pairs(p,4));
    
    % Cumulative Average Calculation
    diff_signal = M(:,i1) - M(:,i2);
    cumAvg = cumsum(diff_signal) ./ (1:nFrames)';
    
    % === LOG-LOG PLOTTING ===
    % We plot ABS because log scales can't handle negative numbers.
    % If the signal is truly squeezing, it will be positive. 
    % If it's noise oscillating around zero, you'll see "dips" in the log plot.
    loglog(time_axis, abs(scale_to_urad2(cumAvg)), ...
           'Color', colors(p,:), 'LineWidth', 1, 'DisplayName', pairLabels{p});
end

grid on;
xlabel('Integration Time (s) [Log Scale]');
ylabel('Abs(Amplitude) [\mu rad^2] [Log Scale]');
title(sprintf('Convergence at %.2f mm (Log-Log)', TARGET_POS_MM));
subtitle(sprintf('%d Frames | %d Pairs', nFrames, size(pairs,1)));

% Only show legend if fewer than 20 pairs to avoid clutter, else print list to console
if size(pairs,1) <= 20
    legend('Location','bestoutside');
else
    fprintf('Legend suppressed due to high pair count (%d). Check cursor data tips.\n', size(pairs,1));
end

end

function f = find_first(d, n), f=""; for i=1:numel(n), c=fullfile(d,n(i)); if isfile(c), f=c; return; end; end; end
function cm_pipeline_loglog_per_bin(target_folder)
% ==========================================================
% Quantum Squeezing Pipeline: Log-Log Per Bin
% 
% 1. Loads & Filters Data (Variance + Kurtosis).
% 2. Groups data by Motor Position.
% 3. For EACH bin, calculates the Running Mean (Convergence).
% 4. Generates a Log-Log plot for that specific position.
% ==========================================================

%% 1. Config & Setup
if nargin < 1 || isempty(target_folder)
    fprintf('No target folder provided. Opening folder selector...\n');
    startPath = 'D:\Quantum Squeezing Project\DataFiles';
    if ~isfolder(startPath), startPath = pwd; end
    runFolder = uigetdir(startPath, 'Select the Data Run Folder');
    if runFolder == 0, error('Cancelled.'); end
else
    runFolder = target_folder;
end

% Physics Constants
bin_mm         = 0.05;                  
scale_factor   = (0.24^2) / (32768^2); 
frame_dt_s     = 0.025;                
rel_threshold  = 0.20; % Minimum data requirement per bin

% --- Full Pair List ---
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

%% 2. Load Data
fCM = fullfile(runFolder,'cm.bin');
fProfile = fullfile(runFolder,'profile.txt');
fPos = find_first(runFolder, ["delay_stage_positions.log","delay_stage_positions.csv"]);
fSens = fullfile(runFolder,'sensitivity.log');

assert(isfile(fCM), 'cm.bin not found.');

% Load CM
fid=fopen(fCM,'rb'); r=fread(fid,'double'); fclose(fid);
cm = reshape(r,64,[]).' * scale_factor;
[N, ~] = size(cm);

% Load Time
txt=fileread(fProfile); 
tok=regexp(txt,'start timestamp:\s*(\S+)','tokens');
if isempty(tok), tCM=datetime(0,0,0)+milliseconds(0:N-1); else, 
try tCM=datetime([tok{:}],'InputFormat','HH:mm:ss.SSS'); catch, tCM=datetime([tok{:}],'InputFormat','HH:mm:ss.SSSSSS'); end, end
tCM = tCM(1:min(numel(tCM),N));
tCM_s = seconds(tCM - tCM(1));

% Load Positions
if fPos == ""
    posOnCM = ones(N,1) * 25.058;
else
    T=readtable(fPos); pt=T{:,1}; pv=T{:,end};
    if isstring(pt), pt=datetime(pt,'InputFormat','HH:mm:ss.SSS'); end
    if isdatetime(pt), t_pos = timeofday(pt); else, t_pos = pt; end
    if isdatetime(tCM), t_cm = timeofday(tCM(1)); else, t_cm = tCM(1); end
    
    dt = seconds(t_pos - t_cm);
    
    % Clean NaNs before interp
    valid_t = isfinite(dt) & isfinite(pv);
    dt = dt(valid_t); pv = pv(valid_t);
    
    if isempty(dt)
        posOnCM = ones(N,1) * pv(1);
    else
        [pu, ia] = unique(dt); pv = pv(ia);
        if numel(pu) < 2, posOnCM = ones(N,1) * pv(1);
        else, posOnCM = interp1(pu, pv, tCM_s, 'linear', 'extrap'); end
    end
end

% Physics Meta
meta_txt = fileread(fSens);
tok_cf = regexp(meta_txt, 'Conversion Factor\s*=\s*([\d\.E\+\-]+)', 'tokens', 'once');
if isempty(tok_cf), CF = 1e4; else, CF = str2double(tok_cf); end
scale_to_urad2 = @(v) (v ./ CF) * 1e12; 

%% 3. Filters (Variance & Kurtosis)
% A. Variance Gating
rms = std(cm, 0, 2);
cutoff = mean(rms) * 0.5; 
is_dead = rms < cutoff;
cm(is_dead, :) = [];
posOnCM(is_dead) = [];
fprintf('Variance Filter: Removed %d frames.\n', sum(is_dead));

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
fprintf('Kurtosis Filter: Keeping %d pairs.\n', size(pairs,1));

%% 4. Group by Position Bin
posBin = round(posOnCM / bin_mm) * bin_mm;
[binVals, ~, grp] = unique(posBin);
counts = accumarray(grp, 1);

% Keep only bins with enough data
min_count = round(rel_threshold * mean(counts(counts>0)));
keep_bins = counts >= min_count;
binVals = binVals(keep_bins); 
valid_indices = find(keep_bins);
nBins = numel(binVals);

fprintf('\nProcessing %d valid position bins...\n', nBins);

%% 5. Loop Bins and Generate Log-Log Plots
idx_lin = @(r,c) sub2ind([8 8], r, c);
colors = jet(size(pairs,1));

for b = 1:nBins
    currentPos = binVals(b);
    orig_idx = valid_indices(b);
    
    % Extract data for this specific bin
    M = cm(grp == orig_idx, :); 
    nFrames = size(M,1);
    time_axis = (1:nFrames) * frame_dt_s;
    
    fprintf('Generating plot for Bin %.3f mm (%d frames)...\n', currentPos, nFrames);
    
    f = figure('Visible','off','Color','w','Position',[50 50 1000 700]);
    hold on;
    
    for p = 1:size(pairs,1)
        i1 = idx_lin(pairs(p,1), pairs(p,2));
        i2 = idx_lin(pairs(p,3), pairs(p,4));
        
        diff_signal = M(:,i1) - M(:,i2);
        
        % === CORRECT LOGIC ===
        % 1. Cumulative Sum (Accumulates Total)
        % 2. Divide by (1:N) (Normalizes to Average)
        cumAvg = cumsum(diff_signal) ./ (1:nFrames)';
        
        % 3. Plot Absolute on Log-Log
        loglog(time_axis, abs(scale_to_urad2(cumAvg)), ...
               'Color', colors(p,:), 'LineWidth', 1, 'DisplayName', pairLabels{p});
    end
    
    grid on;
    xlabel('Integration Time (s)');
    ylabel('Abs(Mean Amplitude) [\mu rad^2]');
    title(sprintf('Convergence at %.3f mm', currentPos));
    subtitle(sprintf('Log-Log Plot | %d Frames', nFrames));
    
    % Only show legend if readable
    if size(pairs,1) < 25
        legend('Location','bestoutside');
    end
    
    % Save Plot
    fname = fullfile(runFolder, sprintf('loglog_bin_%.3fmm.png', currentPos));
    exportgraphics(f, fname);
    close(f);
end

fprintf('All plots generated successfully.\n');

end

function f = find_first(d, n), f=""; for i=1:numel(n), c=fullfile(d,n(i)); if isfile(c), f=c; return; end; end; end
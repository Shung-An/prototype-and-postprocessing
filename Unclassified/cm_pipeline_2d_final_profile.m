function cm_pipeline_2d_final_profile(target_folder)
% ==========================================================
% Quantum Squeezing Pipeline: 2D FINAL RESULTS
% 
% * GOAL: Show the "Final Clean Result" for every pair.
% * PLOT: X-Axis = Position (mm)
%         Y-Axis = Squeezing Amplitude (urad^2)
% * LOGIC: Takes the mean of the fully integrated signal 
%          at each position step.
% * SAVES: PNG files (Grouped).
% ==========================================================

%% 1. Config & Setup
if nargin < 1 || isempty(target_folder)
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
rel_threshold  = 0.20; 

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
fprintf('Loading data... ');
fCM = fullfile(runFolder,'cm.bin');
fProfile = fullfile(runFolder,'profile.txt');
fPos = find_first(runFolder, ["delay_stage_positions.log","delay_stage_positions.csv"]);
fSens = fullfile(runFolder,'sensitivity.log');

assert(isfile(fCM), 'cm.bin not found.');

% Load CM
fid=fopen(fCM,'rb'); r=fread(fid,'double'); fclose(fid);
cm = reshape(r,64,[]).' * scale_factor;
[N, ~] = size(cm);

% Load Time (for interpolation)
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
    valid_t = isfinite(dt) & isfinite(pv);
    dt = dt(valid_t); pv = pv(valid_t);
    if isempty(dt), posOnCM = ones(N,1) * pv(1);
    else, [pu, ia] = unique(dt); pv = pv(ia);
          if numel(pu)<2, posOnCM=ones(N,1)*pv(1); else, posOnCM=interp1(pu,pv,tCM_s,'linear','extrap'); end
    end
end

meta_txt = fileread(fSens);
tok_cf = regexp(meta_txt, 'Conversion Factor\s*=\s*([\d\.E\+\-]+)', 'tokens', 'once');
if isempty(tok_cf), CF = 1e4; else, CF = str2double(tok_cf); end
scale_to_urad2 = @(v) (v ./ CF) * 1e12; 
fprintf('Done.\n');

%% 3. Filters
rms = std(cm, 0, 2);
cutoff = mean(rms) * 0.5; 
is_dead = rms < cutoff;
cm(is_dead, :) = [];
posOnCM(is_dead) = [];

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
fprintf('Valid pairs: %d\n', size(pairs,1));

%% 4. Process Bins
posBin = round(posOnCM / bin_mm) * bin_mm;
[binVals, ~, grp] = unique(posBin);
counts = accumarray(grp, 1);
keep_bins = counts >= round(rel_threshold * mean(counts(counts>0)));
binVals = binVals(keep_bins); 
valid_indices = find(keep_bins);
nBins = numel(binVals);

%% 5. Calculate Final Clean Results
% Result Matrix: [nBins x nPairs]
final_results = zeros(nBins, size(pairs,1));
idx_lin = @(r,c) sub2ind([8 8], r, c);

fprintf('Calculating final integrated values...\n');

for p = 1:size(pairs,1)
    i1 = idx_lin(pairs(p,1), pairs(p,2));
    i2 = idx_lin(pairs(p,3), pairs(p,4));
    
    for b = 1:nBins
        % Extract ALL data for this bin (no truncation)
        M = cm(grp == valid_indices(b), :);
        
        % Calculate raw difference
        diff_sig = M(:,i1) - M(:,i2);
        
        % The "Final Result" is the mean of the difference squared (Variance)
        % scaled to physics units.
        % Note: mean(diff) is DC offset. We want Variance.
        % Actually, "Squeezing" is usually Variance of (A-B).
        
        % Calculation: Variance of the difference
        var_val = var(diff_sig); 
        
        % Scale to urad^2
        final_results(b, p) = scale_to_urad2(var_val);
    end
end

%% 6. Generate 2D Line Plots
groups = { 1:7, 8:13, 14:18, 19:22, 23:25, 26:27, 28, 29:34, 35:39, 40:43, 44:46, 47:48, 49 };

fprintf('Plotting results...\n');

for g = 1:numel(groups)
    idxList = groups{g};
    idxList = idxList(idxList <= size(pairs,1)); 
    if isempty(idxList), continue; end
    
    nPlots = numel(idxList);
    nRows = ceil(sqrt(nPlots)); nCols = ceil(nPlots/nRows);
    
    fBig = figure('Visible','off','Color','w', 'Position',[50 50 1600 900]);
    tiledlayout(nRows,nCols,'TileSpacing','compact', 'Padding', 'tight');
    
    for k = 1:nPlots
        p = idxList(k);
        Y_Data = final_results(:, p);
        
        nexttile;
        plot(binVals, Y_Data, 'LineWidth', 1.5, 'Color', 'b');
        
        % Formatting
        title(pairLabels{p}, 'Interpreter', 'none', 'FontSize', 10);
        grid on;
        xlim([min(binVals) max(binVals)]);
        
        % Smart Y-Lim to focus on the <1000 region if data permits
        % If data is consistently low, zoom in. If it has a huge peak, cut it.
        max_y = max(Y_Data);
        if max_y > 2000
            ylim([0, 2000]); % Clip massive peaks to see the floor
        else
            ylim([0, max_y * 1.1]);
        end
        
        xlabel('Position (mm)');
        ylabel('Amp (\mu rad^2)');
    end
    
    sgtitle(sprintf('Group %d: Final Squeezing Profile', g), 'FontSize', 14);
    
    outName = fullfile(runFolder, sprintf('profile_2d_group%d.png', g));
    exportgraphics(fBig, outName, 'Resolution', 150);
    fprintf('Saved: %s\n', outName);
    close(fBig);
end

fprintf('Done.\n');

end

function f = find_first(d, n), f=""; for i=1:numel(n), c=fullfile(d,n(i)); if isfile(c), f=c; return; end; end; end
function cm_pipeline_3d_live_viewer(target_folder)
% ==========================================================
% Quantum Squeezing Pipeline: 3D LIVE VIEWER
% 
% 1. Loads & Filters Data.
% 2. Calculates Converged Running Averages (in memory).
% 3. Opens an INTERACTIVE MENU to let you select and view 3D plots.
% 4. Does NOT save files. Does NOT close windows.
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
fprintf('Done.\n');

%% 3. Filters
rms = std(cm, 0, 2);
cutoff = mean(rms) * 0.5; 
is_dead = rms < cutoff;
cm(is_dead, :) = [];
posOnCM(is_dead) = [];

kurt = kurtosis(cm);
bad_chs = find(kurt > 5.0);
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
fprintf('Filters active. %d pairs valid.\n', size(pairs,1));

%% 4. Data Binning & Calculation
fprintf('Calculating convergence matrices... ');
posBin = round(posOnCM / bin_mm) * bin_mm;
[binVals, ~, grp] = unique(posBin);
counts = accumarray(grp, 1);

min_count = round(rel_threshold * mean(counts(counts>0)));
keep_bins = counts >= min_count;
binVals = binVals(keep_bins); 
valid_indices = find(keep_bins);
nBins = numel(binVals);

% Determine uniform frame count for rectangular 3D grid
min_frames = inf;
for b = 1:nBins
    c = sum(grp == valid_indices(b));
    if c < min_frames, min_frames = c; end
end

idx_lin = @(r,c) sub2ind([8 8], r, c);
cumsums = cell(size(pairs,1), nBins); 

for p = 1:size(pairs,1)
    i1 = idx_lin(pairs(p,1), pairs(p,2));
    i2 = idx_lin(pairs(p,3), pairs(p,4));
    
    for b = 1:nBins
        M = cm(grp == valid_indices(b), :); 
        M = M(1:min_frames, :);
        
        diff_sig = M(:,i1) - M(:,i2);
        % Running Average Calculation (Sum / N)
        val = abs(scale_to_urad2(cumsum(diff_sig) ./ (1:min_frames)'));
        cumsums{p,b} = val;
    end
end
fprintf('Done.\n');

%% 5. INTERACTIVE VIEWER LOOP
% Define groups for easier navigation
groups = { 1:7, 8:13, 14:18, 19:22, 23:25, 26:27, 28, 29:34, 35:39, 40:43, 44:46, 47:48, 49 };
time_axis = (1:min_frames) * frame_dt_s;
[X_mesh, Y_mesh] = meshgrid(time_axis, binVals);

while true
    % Create Menu Options
    menuOpts = cell(numel(groups)+1, 1);
    for g = 1:numel(groups)
        p_indices = groups{g};
        valid_p = p_indices(p_indices <= size(pairs,1));
        if isempty(valid_p)
            label = sprintf('Group %d (Empty)', g);
        else
            label = sprintf('Group %d: %s ...', g, pairLabels{valid_p(1)});
        end
        menuOpts{g} = label;
    end
    menuOpts{end} = 'Exit Viewer';
    
    % Show Menu
    choice = menu('Select Data Group to View (3D)', menuOpts);
    
    if choice == numel(menuOpts) || choice == 0
        fprintf('Exiting Viewer.\n');
        break;
    end
    
    % Plot Selected Group
    idxList = groups{choice};
    idxList = idxList(idxList <= size(pairs,1));
    
    if isempty(idxList)
        msgbox('No valid pairs in this group.');
        continue;
    end
    
    nPlots = numel(idxList);
    nRows = ceil(sqrt(nPlots)); nCols = ceil(nPlots/nRows);
    
    % Create Figure (VISIBLE ON)
    f = figure('Name', sprintf('3D Viewer - Group %d', choice), ...
               'Color','w', 'NumberTitle','off');
    
    tiledlayout(nRows, nCols, 'TileSpacing','compact', 'Padding', 'tight');
    
    for k = 1:nPlots
        p = idxList(k);
        
        % Construct Z Matrix
        Z = zeros(nBins, min_frames);
        for b = 1:nBins
            Z(b,:) = cumsums{p,b}'; 
        end
        
        nexttile;
        s = surf(X_mesh, Y_mesh, Z);
        
        % Visuals
        s.EdgeColor = 'none'; 
        s.FaceColor = 'interp';
        colormap jet;
        
        set(gca, 'ZScale', 'log'); 
        view(-45, 30); 
        axis tight; 
        grid on;
        
        title(pairLabels{p}, 'Interpreter', 'none', 'FontSize', 10);
        xlabel('Time (s)');
        ylabel('Pos (mm)');
        zlabel('\mu rad^2 (Log)');
    end
    
    % Add interaction hint
    sgtitle('Use mouse to rotate. Select "Exit" in menu to stop.', 'FontSize', 12);
    rotate3d on;
    
    fprintf('Group %d plotted in new window.\n', choice);
end

end

function f = find_first(d, n), f=""; for i=1:numel(n), c=fullfile(d,n(i)); if isfile(c), f=c; return; end; end; end
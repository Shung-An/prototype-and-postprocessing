function cm_diff_cumsum_by_position
% ==========================================================
% Cumulative sum of pixel differences per (binned) position.
% Pixels: (3,3) - (8,8) and (4,4) - (8,8) on an 8×8 from 64ch.
% Inputs (in selected run folder):
%   cm.bin, profile.txt, delay_stage_positions.(log|csv|txt)
% Output:
%   pos_diff_cumsum.mat  (struct with per-position results)
%   pos_bin_counts.csv   (bin -> count)
% ==========================================================

%% --- Select run folder ---
root = 'Z:\Quantum Squeezing Project\DataFiles';
runFolder = uigetdir(root, 'Select Run Folder');
if runFolder == 0, disp('No folder. Exiting.'); return; end

dataFile    = fullfile(runFolder, 'cm.bin');
profileFile = fullfile(runFolder, 'profile.txt');

%% --- Tunables ---
scale_factor   = (0.24^2) / (32768^2);  % your scaling
pos_step_mm    = 0.01;                  % bin size in mm
contam_chan    = 7;                     % contamination test channel (1-based)
contam_thresh  = 1e-15;
contam_halfwin = 500;                   % +/- frames to blank

%% --- Load 64-ch CM and scale ---
cm = readCM64(dataFile);        % [N x 64]
cm = cm * scale_factor;
[N, nCh] = size(cm); if nCh ~= 64, warning('Expected 64 channels, got %d.', nCh); end

%% --- Read frame timestamps from profile.txt ---
tCM = read_times_from_profile(profileFile, N);      % datetime
L = min(N, numel(tCM)); cm = cm(1:L,:); tCM = tCM(1:L); N = L;

%% --- Read positions & interpolate onto CM times ---
[posTime, posVal] = read_positions_series(runFolder);

t0     = tCM(1);
tCM_s  = seconds(tCM - t0);
pos_s  = seconds(posTime - t0);

[~, ia] = unique(pos_s, 'stable');
pos_sU  = pos_s(ia);
posValU = posVal(ia);
[pos_sU, ord] = sort(pos_sU); posValU = posValU(ord);

posOnCM = interp1(pos_sU, posValU, tCM_s, 'linear', 'extrap');
posOnCM(tCM_s < pos_sU(1))  = posValU(1);
posOnCM(tCM_s > pos_sU(end))= posValU(end);

%% --- Contamination filter on raw frames ---
cIdx = min(max(contam_chan,1), size(cm,2));
bad = false(N,1);
i = 1;
while i <= N
    if abs(cm(i,cIdx)) < contam_thresh && ~bad(i)
        s = max(1, i-contam_halfwin);
        e = min(N, i+contam_halfwin-1);
        bad(s:e) = true; i = e + 1;
    else
        i = i + 1;
    end
end
cm      = cm(~bad,:); 
tCM     = tCM(~bad);
tCM_s   = tCM_s(~bad);
posOnCM = posOnCM(~bad);
N       = size(cm,1);

%% --- Bin positions and group indices ---
posBin = round(posOnCM / pos_step_mm) * pos_step_mm;
[binVals, ~, grp] = unique(posBin);         % grp ∈ [1..nBins]
nBins = numel(binVals);

%% --- Prepare indices for pixels (3,3), (4,4), (8,8) ---
idx_33 = sub2ind([8 8], 3, 3);   % = 19
idx_44 = sub2ind([8 8], 4, 4);   % = 28
idx_88 = sub2ind([8 8], 8, 8);   % = 64

%% --- Compute cumulative sums per bin (time order within the bin) ---
counts = zeros(nBins,1);
cumsum_33m88 = cell(nBins,1);   % each is [Kx1]
cumsum_44m88 = cell(nBins,1);   % each is [Kx1]

for b = 1:nBins
    idx = find(grp == b);              % indices of frames in this bin (time order preserved)
    counts(b) = numel(idx);
    if counts(b) == 0
        cumsum_33m88{b} = zeros(0,1);
        cumsum_44m88{b} = zeros(0,1);
        continue;
    end
    % For each frame -> extract 64ch, pick the three pixels
    v33 = cm(idx, idx_33);
    v44 = cm(idx, idx_44);
    v88 = cm(idx, idx_88);

    d33 = v33 - v88;
    d44 = v44 - v88;

    cumsum_33m88{b} = cumsum(d33);
    cumsum_44m88{b} = cumsum(d44);
end

%% --- Save compact MAT and a small counts CSV ---
outMat = fullfile(runFolder, 'pos_diff_cumsum.mat');
result = struct();
result.bin_step_mm   = pos_step_mm;
result.bin_values    = binVals;            % [nBins x 1]
result.counts        = counts;             % [nBins x 1]
result.cumsum_33m88  = cumsum_33m88;       % {nBins x 1}, each [Kx1] in acquisition order
result.cumsum_44m88  = cumsum_44m88;       % {nBins x 1}, each [Kx1]
result.idx_pixels    = struct('p33',idx_33,'p44',idx_44,'p88',idx_88);
result.time0         = t0;
save(outMat, 'result', '-v7.3');
fprintf('Saved: %s\n', outMat);

writematrix([binVals, counts], fullfile(runFolder,'pos_bin_counts.csv'));
fprintf('Saved: %s\n', fullfile(runFolder,'pos_bin_counts.csv'));

disp('Done.');
end

% ----------------------- Helpers -----------------------

function cm = readCM64(filename)
    fid = fopen(filename,'rb'); assert(fid~=-1,'Cannot open %s',filename);
    raw = fread(fid,'double'); fclose(fid);
    assert(mod(numel(raw),64)==0,'Data length not multiple of 64 doubles.');
    cm = reshape(raw, 64, []).';   % [N x 64], column-major mapping to 8x8
end

function tvec = read_times_from_profile(filename, N_expected)
    txt = fileread(filename);
    tokens = regexp(txt,'Transfer start timestamp:\s*([0-2]\d:[0-5]\d:[0-5]\d\.\d+)','tokens');
    assert(~isempty(tokens),'No timestamps found in %s',filename);
    ts = strings(numel(tokens),1);
    for k=1:numel(tokens), ts(k) = string(tokens{k}{1}); end
    if numel(ts) ~= N_expected
        warning('profile timestamps (%d) != cm frames (%d). Using min.', numel(ts), N_expected);
        ts = ts(1:min(numel(ts),N_expected));
    end
    try
        tvec = datetime(ts,'InputFormat','HH:mm:ss.SSS','Format','HH:mm:ss.SSS');
    catch
        tvec = datetime(ts,'InputFormat','HH:mm:ss.SSSSSS','Format','HH:mm:ss.SSS');
    end
end

function [posTime, posVal] = read_positions_series(runFolder)
    pats = ["delay_stage_positions.log","delay_stage_positions.csv","delay_stage_positions.txt"];
    f = "";
    for p = pats
        cand = fullfile(runFolder,p);
        if isfile(cand), f = cand; break; end
    end
    if f == "", error('delay_stage_positions.* not found in %s', runFolder); end

    try
        opts = detectImportOptions(f);
        T = readtable(f, opts);
        T.Properties.VariableNames = strrep(T.Properties.VariableNames,' ','_');
        if ~ismember('Timestamp',T.Properties.VariableNames), T.Timestamp = T{:,1}; end
        if ~ismember('Position', T.Properties.VariableNames), T.Position  = T{:,end}; end
        tsStr = string(T.Timestamp); tsStr = strtrim(tsStr);
        tsStr = regexprep(tsStr,'^.*?(\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?).*$','$1');
        pos   = T.Position;
        if iscell(pos) || isstring(pos), pos = str2double(string(pos)); end
        posTime = datetime(tsStr,'InputFormat','HH:mm:ss.SSS','Format','HH:mm:ss.SSS');
        posVal  = double(pos);
        good = ~isnat(posTime) & ~isnan(posVal);
        posTime = posTime(good); posVal = posVal(good);
        if isempty(posTime), error('Positions empty after cleaning.'); end
    catch
        txt = fileread(f);
        toks = regexp(txt,'(\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?)\s*[,;\s]\s*([+-]?\d+(?:\.\d+)?)','tokens');
        assert(~isempty(toks),'Could not parse %s',f);
        n = numel(toks);
        posTime = NaT(n,1); posVal = zeros(n,1);
        for i=1:n
            posTime(i) = datetime(toks{i}{1},'InputFormat','HH:mm:ss.SSS');
            posVal(i)  = str2double(toks{i}{2});
        end
    end
end

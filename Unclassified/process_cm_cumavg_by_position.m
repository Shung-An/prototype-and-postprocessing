function process_cm_cumavg_by_position
% ==========================================================
% Fast pipeline: cumulative average per (binned) position
% Inputs (in selected folder):
%   - cm.bin                          (64 doubles per frame)
%   - profile.txt                     (timestamps; "Transfer start timestamp: HH:MM:SS.mmm")
%   - delay_stage_positions.(log|csv|txt)  (Timestamp,Position)
%
% Outputs in the same folder:
%   - pos_cumavg_summary.mat   (struct with bins, counts, final means, cumulative means per bin)
%   - pos_final_mean.csv       (per-bin final mean per channel)
%   - pos_counts.csv           (frame counts per bin)
% ==========================================================

%% === Select run folder ===
defaultFolder = 'Z:\Quantum Squeezing Project\DataFiles';
runFolder = uigetdir(defaultFolder, 'Select Run Folder');
if runFolder == 0, disp('No folder. Exiting.'); return; end

dataFile    = fullfile(runFolder, 'cm.bin');
profileFile = fullfile(runFolder, 'profile.txt');
titleFile   = fullfile(runFolder, 'file_description.log');

%% === Parameters you may tweak ===
scale_factor   = (0.24^2) / (32768^2);  % your original scaling
pos_step_mm    = 0.01;                  % bin size in mm (e.g., 0.01 mm)
contam_chan    = 7;                     % channel used for contamination mask
contam_thresh  = 1e-15;                 % threshold on that channel (abs)
contam_halfwin = 500;                   % +/- samples to blank when triggered

%% === Load CM (64ch) fast ===
cm = readCM64(dataFile);            % [N x 64]
cm = cm * scale_factor;
[N, nCh] = size(cm);
if nCh ~= 64
    warning('Expected 64 channels, found %d. Proceeding.', nCh);
end

%% === Timestamps from profile.txt ===
tCM = read_times_from_profile(profileFile, N);  % datetime length N
% Trim to min length just in case
L = min(N, numel(tCM));
cm = cm(1:L, :);
tCM = tCM(1:L);
N   = L;

%% === Read stage positions and interpolate to CM timestamps ===
[posTime, posVal] = read_positions_series(runFolder);
% Time bases in seconds from first CM timestamp
t0     = tCM(1);
tCM_s  = seconds(tCM - t0);
pos_s  = seconds(posTime - t0);

% Unique+sorted for interp
[~, ia] = unique(pos_s, 'stable');
pos_sU  = pos_s(ia);
posValU = posVal(ia);
[pos_sU, ord] = sort(pos_sU);
posValU       = posValU(ord);

% Interpolate (linear) and clamp edges
posOnCM = interp1(pos_sU, posValU, tCM_s, 'linear', 'extrap');
posOnCM(tCM_s < pos_sU(1))  = posValU(1);
posOnCM(tCM_s > pos_sU(end))= posValU(end);

%% === Contamination filter (on raw frames) ===
cIdx = min(max(contam_chan,1), nCh); % clamp channel index
bad = false(N,1);
i = 1;
while i <= N
    if abs(cm(i, cIdx)) < contam_thresh && ~bad(i)
        s = max(1, i-contam_halfwin);
        e = min(N, i+contam_halfwin-1);
        bad(s:e) = true; i = e + 1;
    else
        i = i + 1;
    end
end
% Apply mask
cm       = cm(~bad, :);
tCM      = tCM(~bad);
tCM_s    = tCM_s(~bad);
posOnCM  = posOnCM(~bad);
N        = size(cm,1);

%% === Bin positions and group indices ===
posBin = round(posOnCM / pos_step_mm) * pos_step_mm;    % scalar binning
[binVals, ~, grp] = unique(posBin);                     % grp ∈ [1..nBins]
nBins = numel(binVals);

%% === Cumulative average per position bin (fast) ===
% We’ll build a cell array: cumMean{b} is [K_b x nCh] cumulative means
cumMean = cell(nBins, 1);
finalMean = zeros(nBins, nCh);
counts    = zeros(nBins, 1);

for b = 1:nBins
    idx = find(grp == b);
    counts(b) = numel(idx);
    if counts(b) == 0
        cumMean{b} = zeros(0, nCh);
        continue;
    end
    % running mean: cumsum / (1:K)
    cs = cumsum(cm(idx, :), 1);                % [K x nCh]
    denom = (1:counts(b))';                     % [K x 1]
    cumMean{b} = cs ./ denom;                   % [K x nCh]
    finalMean(b, :) = cumMean{b}(end, :);
end

%% === Save compact result (MAT) ===
summary = struct();
summary.bin_step_mm = pos_step_mm;
summary.bin_values  = binVals;       % [nBins x 1] positions
summary.counts      = counts;        % [nBins x 1]
summary.final_mean  = finalMean;     % [nBins x nCh]
summary.cum_mean    = cumMean;       % {nBins x 1}, each [K_b x nCh]
summary.channels    = nCh;
summary.t0          = t0;
summary.notes       = "Cumulative average per position bin over arrival order";

save(fullfile(runFolder, 'pos_cumavg_summary.mat'), 'summary', '-v7.3');
fprintf('Saved: %s\n', fullfile(runFolder, 'pos_cumavg_summary.mat'));

%% === Optional CSVs for quick inspection ===
% Per-bin final mean and counts
fn_mean  = fullfile(runFolder, 'pos_final_mean.csv');
fn_count = fullfile(runFolder, 'pos_counts.csv');
writematrix([binVals, finalMean], fn_mean);
writematrix([binVals, counts],    fn_count);
fprintf('Saved: %s, %s\n', fn_mean, fn_count);

%% === (Optional) sanity print ===
fprintf('Bins: %d  | Frames: %d  | Avg frames/bin: %.2f\n', nBins, N, mean(counts));

end

% ======================= Helpers =======================

function cm = readCM64(filename)
    fid = fopen(filename,'rb');
    assert(fid~=-1, 'Cannot open %s', filename);
    raw = fread(fid, 'double'); fclose(fid);
    assert(mod(numel(raw),64)==0, 'Data length is not multiple of 64 doubles.');
    cm = reshape(raw, 64, []).';   % [N x 64]
end

function tvec = read_times_from_profile(filename, N_expected)
% Extract "Transfer start timestamp: HH:MM:SS.mmm" from profile.txt
    txt = fileread(filename);
    tokens = regexp(txt, 'Transfer start timestamp:\s*([0-2]\d:[0-5]\d:[0-5]\d\.\d+)', 'tokens');
    assert(~isempty(tokens), 'No timestamps found in %s', filename);
    ts = strings(numel(tokens),1);
    for i=1:numel(tokens), ts(i) = string(tokens{i}{1}); end
    if numel(ts) ~= N_expected
        warning('profile timestamps (%d) != cm frames (%d). Using min length.', numel(ts), N_expected);
        ts = ts(1:min(numel(ts),N_expected));
    end
    % Accept variable fractional digits
    try
        tvec = datetime(ts, 'InputFormat','HH:mm:ss.SSS', 'Format','HH:mm:ss.SSS');
    catch
        tvec = datetime(ts, 'InputFormat','HH:mm:ss.SSSSSS', 'Format','HH:mm:ss.SSS');
    end
end

function [posTime, posVal] = read_positions_series(runFolder)
% Find and parse delay_stage_positions.(log|csv|txt) -> vectors
    pats = ["delay_stage_positions.log","delay_stage_positions.csv","delay_stage_positions.txt"];
    f = "";
    for p = pats
        cand = fullfile(runFolder, p);
        if isfile(cand), f = cand; break; end
    end
    if f == "", error('delay_stage_positions.* not found in %s', runFolder); end

    % Try a table read first
    try
        opts = detectImportOptions(f);
        T = readtable(f, opts);
        T.Properties.VariableNames = strrep(T.Properties.VariableNames,' ','_');
        if ~ismember('Timestamp', T.Properties.VariableNames), T.Timestamp = T{:,1}; end
        if ~ismember('Position',  T.Properties.VariableNames), T.Position  = T{:,end}; end
        tsStr = string(T.Timestamp); tsStr = strtrim(tsStr);
        % Keep only HH:MM:SS(.fff…)
        tsStr = regexprep(tsStr,'^.*?(\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?).*$','$1');
        pos   = T.Position;
        if iscell(pos) || isstring(pos), pos = str2double(string(pos)); end
        posTime = datetime(tsStr,'InputFormat','HH:mm:ss.SSS','Format','HH:mm:ss.SSS');
        posVal  = double(pos);
        good = ~isnat(posTime) & ~isnan(posVal);
        posTime = posTime(good); posVal = posVal(good);
        if isempty(posTime), error('Positions empty after cleaning.'); end
        return
    catch
        % Fallback: regex raw text
        txt = fileread(f);
        toks = regexp(txt,'(\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?)\s*[,;\s]\s*([+-]?\d+(?:\.\d+)?)','tokens');
        assert(~isempty(toks), 'Could not parse %s', f);
        n = numel(toks);
        posTime = NaT(n,1); posVal = zeros(n,1);
        for i=1:n
            posTime(i) = datetime(toks{i}{1},'InputFormat','HH:mm:ss.SSS');
            posVal(i)  = str2double(toks{i}{2});
        end
    end
end

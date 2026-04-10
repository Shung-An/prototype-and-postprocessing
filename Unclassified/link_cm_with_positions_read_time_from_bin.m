function link_cm_interpolate_positions_profile
%% === Select run folder ===
defaultFolder = 'Z:\Quantum Squeezing Project\DataFiles';
folderOut = uigetdir(defaultFolder, 'Select Result Folder');
if folderOut == 0, disp('No folder selected. Exiting.'); return; end

dataFile   = fullfile(folderOut, 'cm.bin');       % 64-ch doubles
profileFile= fullfile(folderOut, 'profile.txt');  % timestamps source
titleFile  = fullfile(folderOut, 'file_description.log');

[extraTitle, ~] = readDescriptionFile(titleFile);

%% === Load CM (64ch) and scale ===
cm = readCM64(dataFile);            % [N x 64]
cm = cm / 32768^2 * 0.24^2;
N  = size(cm,1);

%% === Read frame timestamps from profile.txt ===
tCM = read_times_from_profile(profileFile, N);  % datetime length N (HH:mm:ss.SSS)

% Convert to seconds from first time (monotonic base for interp)
t0   = tCM(1);
tCMs = seconds(tCM - t0);

%% === Read stage positions and make clean time/value vectors ===
[posTime, posVal] = read_positions_series(folderOut);
posSec = seconds(posTime - t0);

% Ensure strictly increasing independent var for interp1
[ posSecU, ia ] = unique(posSec, 'stable');
posValU = posVal(ia);
[ posSecU, ord ] = sort(posSecU);
posValU = posValU(ord);

% === Interpolate positions at each CM timestamp ===
posOnCM = interp1(posSecU, posValU, tCMs, 'linear', 'extrap');
% clamp edges to nearest real value (avoid extrap drift)
leftMask  = tCMs < posSecU(1);   if any(leftMask),  posOnCM(leftMask)  = posValU(1);   end
rightMask = tCMs > posSecU(end); if any(rightMask), posOnCM(rightMask) = posValU(end); end

%% === Build timetable & contamination filtering ===
cmTT  = array2timetable(cm, 'RowTimes', tCM);
cmTT.Properties.VariableNames = compose("C%02d", 1:64);
cmTT.Position = posOnCM;

% Contamination on C07 ±500 samples
threshold = 1e-15; winHalf = 500;
bad = false(height(cmTT),1); i = 1;
while i <= height(cmTT)
    if abs(cmTT.C07(i)) < threshold && ~bad(i)
        s = max(1, i-winHalf); e = min(height(cmTT), i+winHalf-1);
        bad(s:e) = true; i = e + 1;
    else
        i = i + 1;
    end
end
cmTT = cmTT(~bad,:);

%% === Save merged CSV ===
mergedTbl = timetable2table(cmTT, 'ConvertRowTimes', true);
mergedTbl.Properties.VariableNames{1} = 'Timestamp';
writetable(mergedTbl, fullfile(folderOut, 'cm_with_position.csv'));
fprintf('Saved -> %s\n', fullfile(folderOut, 'cm_with_position.csv'));

%% === Plots (same as before) ===
tsec = seconds(cmTT.Time - cmTT.Time(1));
n = numel(tsec);
acu = cumsum(cmTT{:,1:64}) ./ (1:n)';

% Running mean (semi-log)
f_all = figure('Visible','off','Position',[80 80 1100 700]); hold on;
for k = 1:64
    y = abs(acu(:,k)); y(y<=0) = NaN;
    semilogy(tsec, y);
end
set(gca,'YScale','log'); grid on;
xlabel('Time (s)'); ylabel('Abs Running Mean (V)');
title(['Running Mean for All Channels - ' extraTitle]);
xlim([tsec(1), tsec(end)*1.1]); legend('off');
saveas(f_all, fullfile(folderOut,'semilogy_64channels_time.png')); close(f_all);

% Log-log: (1,1),(3,3),(4,4) minus (8,8) after 400 s
idx_11 = sub2ind([8 8],1,1); idx_33 = sub2ind([8 8],3,3);
idx_44 = sub2ind([8 8],4,4); idx_88 = sub2ind([8 8],8,8);
start_idx = find(tsec >= 400, 1, 'first');
if ~isempty(start_idx)
    tt = tsec(start_idx:end); tt = tt - tt(1); L = numel(tt);
    d11 = cmTT{start_idx:end, idx_11} - cmTT{start_idx:end, idx_88};
    d33 = cmTT{start_idx:end, idx_33} - cmTT{start_idx:end, idx_88};
    d44 = cmTT{start_idx:end, idx_44} - cmTT{start_idx:end, idx_88};
    a11 = cumsum(d11)./(1:L)'; a33 = cumsum(d33)./(1:L)'; a44 = cumsum(d44)./(1:L)';

    f = figure('Visible','off','Position',[90 90 850 600]); hold on;
    loglog(tt,abs(a11),'g-','LineWidth',1.5);
    loglog(tt,abs(a33),'r-','LineWidth',1.5);
    loglog(tt,abs(a44),'b-','LineWidth',1.5);
    set(gca,'XScale','log','YScale','log'); grid on;
    xlabel('Time (s)'); ylabel('Abs Running Mean (V)');
    title('Log-Log Accumulative Mean Differences (t > 400 s)');
    if L>=2, xlim([max(tt(2),1e-3), tt(end)]); end
    ylim([1e-11, 1e-7]);
    saveas(f, fullfile(folderOut,'loglog_diff_11_33_44_minus_88.png')); close(f);
end

% Heatmaps
mmean = mean(cmTT{:,1:64},1); mmse = mean((cmTT{:,1:64}-mmean).^2,1);
mean_8x8 = reshape(mmean,8,8); mse_8x8 = reshape(mmse,8,8);
f1 = figure('Visible','off','Position',[100,100,1200,500]); tiledlayout(1,2,'TileSpacing','Compact');
nexttile; h1 = heatmap(mean_8x8,'ColorbarVisible','on'); h1.CellLabelFormat='%.2e'; title(['Mean Corr (V^2) - ' extraTitle]); colormap(jet);
nexttile; h2 = heatmap(mse_8x8,'ColorbarVisible','on');  h2.CellLabelFormat='%.2e'; title(['MSE Corr (V^4) - ' extraTitle]);  colormap(jet);
saveas(f1, fullfile(folderOut,'combined_heatmap.png')); close(f1);

% Diagonal tail-offset
diag_offset = zeros(8,8);
for d=-7:7
    v = diag(mean_8x8,d); if isempty(v), continue; end
    tail = v(end);
    for k=1:numel(v)
        if d>=0, i=k; j=k+d; else, i=k-d; j=k; end
        diag_offset(i,j) = mean_8x8(i,j) - tail;
    end
end
f2 = figure('Visible','off','Position',[120,120,600,500]);
h = heatmap(diag_offset,'ColorbarVisible','on'); h.CellLabelFormat='%.2e';
title(['Diagonal Tail-Offset Matrix - ' extraTitle]); colormap(jet);
saveas(f2, fullfile(folderOut,'diagonal_offset_matrix.png')); close(f2);

disp('All done.');
end

%% ======================= Helpers =======================

function cm = readCM64(filename)
    fid = fopen(filename,'rb'); assert(fid~=-1, 'Cannot open %s', filename);
    raw = fread(fid, 'double'); fclose(fid);
    assert(mod(numel(raw),64)==0, 'Data length not multiple of 64.');
    cm = reshape(raw, 64, []).';
end

function tvec = read_times_from_profile(filename, N_expected)
% profile.txt lines like:
% "Transfer start timestamp: 12:55:35.192 ,One Step Time: 9.34 ms, ..."
    txt = fileread(filename);
    % capture HH:MM:SS.xxx after 'Transfer start timestamp:'
    tokens = regexp(txt, 'Transfer start timestamp:\s*([0-2]\d:[0-5]\d:[0-5]\d\.\d+)', 'tokens');
    assert(~isempty(tokens), 'No timestamps found in %s', filename);

    ts = strings(numel(tokens),1);
    for i=1:numel(tokens), ts(i) = string(tokens{i}{1}); end

    % If counts mismatch, trim to min length to stay in lockstep with cm.bin
    if numel(ts) ~= N_expected
        warning('profile timestamps (%d) != cm frames (%d). Using min length.', numel(ts), N_expected);
        L = min(numel(ts), N_expected);
        ts = ts(1:L);
    end

    tvec = datetime(ts, 'InputFormat','HH:mm:ss.SSS', 'Format','HH:mm:ss.SSS');
    % If fractional seconds vary in digits, the above still works;
    % otherwise expand InputFormat to 'HH:mm:ss.SSSSSS'.
end

function [posTime, posVal] = read_positions_series(runFolder)
    % Find delay_stage_positions file
    pats = ["delay_stage_positions.log","delay_stage_positions.csv","delay_stage_positions.txt"];
    f = "";
    for p = pats
        cand = fullfile(runFolder, p);
        if isfile(cand), f = cand; break; end
    end
    if f == "", error('delay_stage_positions.* not found in %s', runFolder); end

    % Try table read first
    try
        opts = detectImportOptions(f);
        T = readtable(f, opts);
        T.Properties.VariableNames = strrep(T.Properties.VariableNames,' ','_');
        if ~ismember('Timestamp', T.Properties.VariableNames), T.Timestamp = T{:,1}; end
        if ~ismember('Position',  T.Properties.VariableNames), T.Position  = T{:,end}; end

        tsStr = string(T.Timestamp); tsStr = strtrim(tsStr);
        tsStr = regexprep(tsStr,'^.*?(\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?).*$','$1');
        pos   = T.Position;
        if iscell(pos) || isstring(pos), pos = str2double(string(pos)); end

        posTime = datetime(tsStr,'InputFormat','HH:mm:ss.SSS','Format','HH:mm:ss.SSS');
        posVal  = double(pos);
        good = ~isnat(posTime) & ~isnan(posVal);
        posTime = posTime(good); posVal = posVal(good);
        if isempty(posTime), error('empty after cleaning'); end
    catch
        % Fallback regex (Timestamp,Position)
        txt = fileread(f);
        toks = regexp(txt,'(\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?)\s*[,;\s]\s*([+-]?\d+(?:\.\d+)?)','tokens');
        assert(~isempty(toks), 'Could not parse %s', f);
        posTime = NaT(numel(toks),1); posVal = zeros(numel(toks),1);
        for i=1:numel(toks)
            posTime(i) = datetime(toks{i}{1},'InputFormat','HH:mm:ss.SSS');
            posVal(i)  = str2double(toks{i}{2});
        end
    end
end

function [plotTitle, legendLabel] = readDescriptionFile(filepath)
    plotTitle = ''; legendLabel = '';
    if isfile(filepath)
        fid = fopen(filepath,'r'); L = textscan(fid,'%s','Delimiter','\n'); fclose(fid);
        L = L{1};
        for i=1:numel(L)
            s = strtrim(L{i});
            if startsWith(s,'Filename:'),    legendLabel = strtrim(erase(s,'Filename:'));
            elseif startsWith(s,'Description:'), plotTitle = strtrim(erase(s,'Description:'));
            end
        end
        if ~isempty(plotTitle) && ~isempty(legendLabel)
            plotTitle = [plotTitle ' (' legendLabel ')'];
        elseif isempty(plotTitle)
            plotTitle = legendLabel;
        end
    end
end

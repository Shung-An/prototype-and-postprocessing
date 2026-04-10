% Folder paths to process
folders = {
    'C:\Quantum Squeezing\Quantum-Measurement-Software\results\20250708_184059'
    'C:\Quantum Squeezing\Quantum-Measurement-Software\results\20250707_190025'



    };

row_labels = ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8"];
col_labels= ["B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8"];

for fileIdx = 1:length(folders)
    folderOut = folders{fileIdx};
    dataFile = fullfile(folderOut, 'cm.bin');
    titleFile = fullfile(folderOut, 'file_description.log');
    [extraTitle, legendLabel] = readDescriptionFile(titleFile);


    % Get folder name
    [~, foldername] = fileparts(folderOut);

    % % Try to read title.txt
    % if isfile(titleFile)
    %     extraTitle = strtrim(fileread(titleFile));
    % else
    %     extraTitle = '';
    % end

    % Load data
    data = readCM(dataFile);
    data = data / 32768 / 32768 * 0.24 * 0.24;

    % === Contamination Detection ===
    threshold = 1e-15;
    contaminated = false(size(data,1), 1);
    i = 1;
    while i <= size(data,1)
        if abs(data(i,7)) < threshold && ~contaminated(i)
            % Open new discard window centered at i
            start_idx = max(1, i - 500);
            end_idx = min(size(data,1), i + 499);
            contaminated(start_idx:end_idx) = true;
            i = end_idx + 1; % skip past this window
        else
            i = i + 1;
        end
    end

    clean_data = data(~contaminated, :);

% === Accumulative Sum for All 64 Channels (No pairing) ===
n = size(clean_data, 1);  % number of time steps
acu_sums_64 = zeros(n, 64);

for ch = 1:64
    ch_data = clean_data(:, ch);
    acu_sums_64(:, ch) = cumsum(ch_data) ./ (1:n)';
end

% === Semilogy Plot: Time X, Log Y with (row, col) Labels ===
f_all = figure('Visible', 'off');
hold on;
lines = gobjects(64, 1);  % Preallocate
xvals = (1:n)' * 0.025;  % ⏱ Each sample = 25 ms

idx = 1;
for row = 1:8
    for col = 1:8
        yvals = abs(acu_sums_64(:, idx));
        yvals(yvals <= 0) = NaN;  % prevent log(0)
        lines(idx) = semilogy(xvals, yvals, 'DisplayName', sprintf('(%d,%d)', row, col));

        % Annotate at the end
        if all(isnan(yvals))
            idx = idx + 1;
            continue;
        end
        x_end = xvals(end);
        y_end = yvals(end);
        if ~isnan(y_end) && isfinite(y_end)
            text(x_end * 1.02, y_end, sprintf('(%d,%d)', row, col), ...
                'FontSize', 6, 'Color', lines(idx).Color, ...
                'VerticalAlignment', 'middle');
        end

        idx = idx + 1;
    end
end

set(gca, 'YScale', 'log');
set(gca, 'XScale', 'linear');
xlabel('Time (s)');
ylabel('Absolute Accumulative Mean (V)');
title(['Running Mean for All Channels - ' extraTitle]);
legend('off');
grid on;
xlim([xvals(1), xvals(end) * 1.1]);
saveas(f_all, fullfile(folderOut, 'semilogy_64channels_time_corrected.png'));
close(f_all);

idx_11 = 1;  % (1,1)
idx_33 = (3-1)*8 + 3;  % 19
idx_44 = (4-1)*8 + 4;  % 28
idx_88 = 64;  % (8,8)

% Start index after 400 samples
start_idx = 401/0.025;
n_tail = size(clean_data, 1) - start_idx + 1;
time_full = ((1:size(clean_data, 1))' - 1) * 0.025;
time_tail = time_full(start_idx:end);
time_tail = time_tail - time_tail(1);  % ⏱️ start at 0

% Compute differences after 400
diff_11_88 = clean_data(start_idx:end, idx_11) - clean_data(start_idx:end, idx_88);
diff_33_88 = clean_data(start_idx:end, idx_33) - clean_data(start_idx:end, idx_88);
diff_44_88 = clean_data(start_idx:end, idx_44) - clean_data(start_idx:end, idx_88);

% Cumulative mean
acu_11_88 = cumsum(diff_11_88) ./ (1:n_tail)';
acu_33_88 = cumsum(diff_33_88) ./ (1:n_tail)';
acu_44_88 = cumsum(diff_44_88) ./ (1:n_tail)';

% Avoid zeros
acu_11_88(acu_11_88 == 0) = NaN;
acu_33_88(acu_33_88 == 0) = NaN;
acu_44_88(acu_44_88 == 0) = NaN;

% === Plot updated log-log ===
f_loglog = figure('Visible', 'off');
hold on;
loglog(time_tail, abs(acu_11_88), 'g-', 'LineWidth', 1.5, 'DisplayName', '(1,1)-(8,8)');
loglog(time_tail, abs(acu_33_88), 'r-', 'LineWidth', 1.5, 'DisplayName', '(3,3)-(8,8)');
loglog(time_tail, abs(acu_44_88), 'b-', 'LineWidth', 1.5, 'DisplayName', '(4,4)-(8,8)');
set(gca, 'XScale', 'log', 'YScale', 'log');
xlabel('Time (s)');
ylabel('Abs Running Mean (V)');
title('Log-Log Plot of Accumulative Mean Differences (from t > 400s)');
legend('Location', 'northeast');
xlim([time_tail(2), time_tail(end)]);
ylim([1e-11 ,1e-7 ]);
saveas(f_loglog, fullfile(folderOut, 'loglog_diff_33_44_minus_88.png'));
close(f_loglog);

    %%
    % === Mean & MSE Calculation ===
    matrix1 = mean(clean_data);
    mse = mean((clean_data - matrix1).^2);
    matrix1_8x8 = reshape(matrix1, 8, 8);
    matrix2_8x8 = reshape(mse, 8, 8);
    if fileIdx == 1
        matrix1_ref = matrix1_8x8;

    else
        matrix1_aom = matrix1_8x8;

    end

    % === Combined Heatmap Plot ===
    f1 = figure('Visible', 'off', 'Position', [100, 100, 1200, 500]);
    tiledlayout(1,2, 'TileSpacing', 'Compact');

    % Mean
    nexttile;
    h1 = heatmap(matrix1_8x8, 'ColorbarVisible', 'on');
    h1.XDisplayLabels = col_labels;
    h1.YDisplayLabels = row_labels;
    h1.CellLabelFormat = '%.2e';
    title(['Mean Corr (V^2) - ' extraTitle]);  % ✅ dynamic title
    colormap(jet);

    % MSE
    nexttile;
    h2 = heatmap(matrix2_8x8, 'ColorbarVisible', 'on');
    h2.XDisplayLabels = col_labels;
    h2.YDisplayLabels = row_labels;
    h2.CellLabelFormat = '%.2e';
    title(['MSE Corr (V^4) - ' extraTitle]);  % ✅ also dynamic
    colormap(jet);


    saveas(f1, fullfile(folderOut, 'combined_heatmap.png'));
    close(f1);


    % === Log-Log Time Series of Channel 2 ===
    column_data = clean_data(:, 2);
    column_data(2:2:end) = -column_data(2:2:end);
    n = length(column_data);
    pair_sums = zeros(1, floor(n/2));
    cumulative_sum = 0;
    acu_pair_sums = zeros(1, floor(n/2));
    for i = 1:floor(n/2)
        pair_sums(i) = column_data(2*i-1) + column_data(2*i);
        cumulative_sum = cumulative_sum + pair_sums(i);
        acu_pair_sums(i) = cumulative_sum / i;
    end

    if fileIdx == 1
        abs_acu_pair_sums1 = abs(acu_pair_sums);
        loglog_name1 = legendLabel;

        loglog_path1 = folderOut;
    else
        abs_acu_pair_sums2 = abs(acu_pair_sums);
        loglog_name2 = legendLabel;

        loglog_path2 = folderOut;
    end
end


% === AOM - Comparison Difference Heatmaps ===
diff_mean = matrix1_aom - matrix1_ref;

f_diff = figure('Visible', 'off', 'Position', [100, 100, 1200, 500]);
tiledlayout(1,2, 'TileSpacing', 'Compact');

% Mean Difference
nexttile;
h1 = heatmap(diff_mean, 'ColorbarVisible', 'on');
h1.XDisplayLabels = col_labels;
h1.YDisplayLabels = row_labels;
h1.CellLabelFormat = '%.2e';
title('ΔMean (AOM - No AOM) (V^2)');
colormap(jet);

saveas(f_diff, fullfile(loglog_path1, 'difference_heatmaps.png'));
saveas(f_diff, fullfile(loglog_path2, 'difference_heatmaps.png'));
close(f_diff);


% === Log-Log Plot ===
f2 = figure('Visible', 'off');
loglog(abs_acu_pair_sums1, 'b-', 'DisplayName', loglog_name1);
hold on;
loglog(abs_acu_pair_sums2, 'r-', 'DisplayName', loglog_name2);
title('Log-Log Plot of Absolute Pair Sums (V^2)');
xlabel('Pair Index');
ylabel('Absolute Sum');
legend('show');
grid on;
saveas(f2, fullfile(loglog_path1, 'loglog_plot.png'));
saveas(f2, fullfile(loglog_path2, 'loglog_plot.png'));
close(f2);



function [plotTitle, legendLabel] = readDescriptionFile(filepath)
    plotTitle = '';
    legendLabel = '';
    
    if isfile(filepath)
        fid = fopen(filepath, 'r');
        contents = textscan(fid, '%s', 'Delimiter', '\n');
        fclose(fid);
        lines = contents{1};

        for i = 1:length(lines)
            line = strtrim(lines{i});
            if startsWith(line, 'Filename:')
                legendLabel = strtrim(erase(line, 'Filename:'));
            elseif startsWith(line, 'Description:')
                plotTitle = strtrim(erase(line, 'Description:'));
            end
        end

        % Combine into display title
        if ~isempty(plotTitle) && ~isempty(legendLabel)
            plotTitle = [plotTitle ' (' legendLabel ')'];
        elseif isempty(plotTitle)
            plotTitle = legendLabel;
        end
    end
end


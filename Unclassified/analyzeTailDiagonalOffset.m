%% === Select Folder ===
defaultFolder = 'Z:\Quantum Squeezing Project\DataFiles';
folderOut = uigetdir(defaultFolder, 'Select Result Folder');
if folderOut == 0
    disp('No folder selected. Exiting.');
    return;
end

dataFile = fullfile(folderOut, 'cm.bin');
titleFile = fullfile(folderOut, 'file_description.log');
[extraTitle, legendLabel] = readDescriptionFile(titleFile);

row_labels = ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8"];
col_labels = ["B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8"];

%% === Load and Preprocess Data ===
data = readCM(dataFile);
data = data / 32768^2 * 0.24^2;

% Contamination detection
threshold = 1e-15;
contaminated = false(size(data,1), 1);
i = 1;
while i <= size(data,1)
    if abs(data(i,7)) < threshold && ~contaminated(i)
        start_idx = max(1, i - 500);
        end_idx = min(size(data,1), i + 499);
        contaminated(start_idx:end_idx) = true;
        i = end_idx + 1;
    else
        i = i + 1;
    end
end
clean_data = data(~contaminated, :);

%% === Accumulative Sum for All Channels ===
n = size(clean_data, 1);
acu_sums_64 = zeros(n, 64);
for ch = 1:64
    acu_sums_64(:, ch) = cumsum(clean_data(:, ch)) ./ (1:n)';
end

xvals = (1:n)' * 0.025;
f_all = figure('Visible', 'off');
hold on;
idx = 1;
for row = 1:8
    for col = 1:8
        yvals = abs(acu_sums_64(:, idx));
        yvals(yvals <= 0) = NaN;
        line_obj = semilogy(xvals, yvals, 'DisplayName', sprintf('(%d,%d)', row, col));
        if any(isfinite(yvals))
            text(xvals(end)*1.02, yvals(end), sprintf('(%d,%d)', row, col), ...
                'FontSize', 6, 'Color', line_obj.Color, ...
                'VerticalAlignment', 'middle');
        end
        idx = idx + 1;
    end
end
set(gca, 'YScale', 'log', 'XScale', 'linear');
xlabel('Time (s)'); ylabel('Absolute Accumulative Mean (V)');
title(['Running Mean for All Channels - ' extraTitle]);
grid on;
xlim([xvals(1), xvals(end)*1.1]);
legend('off');
saveas(f_all, fullfile(folderOut, 'semilogy_64channels_time_corrected.png'));
close(f_all);

%% === Loglog Plot: (1,1), (3,3), (4,4) - (8,8) after 400s ===
idx_11 = 1; idx_33 = 19; idx_44 = 28; idx_88 = 64;
start_idx = 5000;
if size(clean_data,1) < start_idx
    warning('Too few clean samples for loglog_diff_33_44_minus_88');
else
    time_tail = ((start_idx:size(clean_data,1))' - 1) * 0.025;
    time_tail = time_tail - time_tail(1);
    n_tail = length(time_tail);

    diff_11_88 = clean_data(start_idx:end, idx_11) - clean_data(start_idx:end, idx_88);
    diff_33_88 = clean_data(start_idx:end, idx_33) - clean_data(start_idx:end, idx_88);
    diff_44_88 = clean_data(start_idx:end, idx_44) - clean_data(start_idx:end, idx_88);

    acu_11_88 = cumsum(diff_11_88) ./ (1:n_tail)';
    acu_33_88 = cumsum(diff_33_88) ./ (1:n_tail)';
    acu_44_88 = cumsum(diff_44_88) ./ (1:n_tail)';

    f_loglog = figure('Visible', 'off');
    hold on;
    loglog(time_tail, abs(acu_11_88), 'g-', 'LineWidth', 1.5, 'DisplayName', '(1,1)-(8,8)');
    loglog(time_tail, abs(acu_33_88), 'r-', 'LineWidth', 1.5, 'DisplayName', '(3,3)-(8,8)');
    loglog(time_tail, abs(acu_44_88), 'b-', 'LineWidth', 1.5, 'DisplayName', '(4,4)-(8,8)');
    set(gca, 'XScale', 'log', 'YScale', 'log');
    xlabel('Time (s)'); ylabel('Abs Running Mean (V)');
    title('Log-Log Plot of Accumulative Mean Differences');
    legend('Location', 'northeast'); grid on;
    if length(time_tail) >= 2
        xlim([time_tail(2), time_tail(end)]);
    else
        xlim([time_tail(1), time_tail(end)]);
    end
    saveas(f_loglog, fullfile(folderOut, 'loglog_diff_33_44_minus_88.png'));
    close(f_loglog);
end

%% === Mean & MSE Heatmap ===
matrix1 = mean(clean_data);
mse = mean((clean_data - matrix1).^2);
matrix1_8x8 = reshape(matrix1, 8, 8);
matrix2_8x8 = reshape(mse, 8, 8);

f1 = figure('Visible', 'off', 'Position', [100, 100, 1200, 500]);
tiledlayout(1,2, 'TileSpacing', 'Compact');
nexttile;
h1 = heatmap(matrix1_8x8, 'ColorbarVisible', 'on');
h1.XDisplayLabels = col_labels;
h1.YDisplayLabels = row_labels;
h1.CellLabelFormat = '%.2e';
title(['Mean Corr (V^2) - ' extraTitle]); colormap(jet);
nexttile;
h2 = heatmap(matrix2_8x8, 'ColorbarVisible', 'on');
h2.XDisplayLabels = col_labels;
h2.YDisplayLabels = row_labels;
h2.CellLabelFormat = '%.2e';
title(['MSE Corr (V^4) - ' extraTitle]); colormap(jet);
saveas(f1, fullfile(folderOut, 'combined_heatmap.png'));
close(f1);

%% === Diagonal Offset Matrix ===
diagonal_offset_matrix = zeros(8, 8);
for d = -7:7
    diag_vals = diag(matrix1_8x8, d);
    if isempty(diag_vals), continue; end
    offset = diag_vals(end);  % tail of the diagonal
    for k = 1:length(diag_vals)
        if d >= 0
            i = k;
            j = k + d;
        else
            i = k - d;
            j = k;
        end
        diagonal_offset_matrix(i, j) = matrix1_8x8(i, j) - offset;
    end
end

f_diag = figure('Visible', 'off', 'Position', [100, 100, 600, 500]);
h_diag = heatmap(diagonal_offset_matrix, 'ColorbarVisible', 'on');
h_diag.XDisplayLabels = col_labels;
h_diag.YDisplayLabels = row_labels;
h_diag.CellLabelFormat = '%.2e';
title(['Diagonal Tail-Offset Matrix - ' extraTitle]);
colormap(jet);
saveas(f_diag, fullfile(folderOut, 'diagonal_offset_matrix.png'));
close(f_diag);

%% === Helper Functions ===
function reshapedData = readCM(filename)
    numElementsPerArray = 64;
    fid = fopen(filename, 'rb');
    if fid == -1, error('Error opening file'); end
    data = fread(fid, 'double'); fclose(fid);
    if mod(length(data), numElementsPerArray) ~= 0
        error('Data length is not a multiple of 64.');
    end
    reshapedData = reshape(data, numElementsPerArray, [])';
end

function [plotTitle, legendLabel] = readDescriptionFile(filepath)
    plotTitle = ''; legendLabel = '';
    if isfile(filepath)
        fid = fopen(filepath, 'r');
        lines = textscan(fid, '%s', 'Delimiter', '\n'); fclose(fid);
        lines = lines{1};
        for i = 1:length(lines)
            line = strtrim(lines{i});
            if startsWith(line, 'Filename:')
                legendLabel = strtrim(erase(line, 'Filename:'));
            elseif startsWith(line, 'Description:')
                plotTitle = strtrim(erase(line, 'Description:'));
            end
        end
        if ~isempty(plotTitle) && ~isempty(legendLabel)
            plotTitle = [plotTitle ' (' legendLabel ')'];
        elseif isempty(plotTitle)
            plotTitle = legendLabel;
        end
    end
end

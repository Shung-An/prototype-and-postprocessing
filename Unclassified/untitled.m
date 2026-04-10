% File paths
file2 = 'C:\Quantum Squeezing\Quantum-Measurement-Software\results\20250526_182805\timeZeroBestFocusSpotOnCam.bin';
file1 = 'C:\Quantum Squeezing\Quantum-Measurement-Software\results\20250527_155712\cm.bin';

% Sampling frequency (you may need to adjust this)
fs = 2623/64;  % Hz

% Process both files
for fileIdx = 1:2
    if fileIdx == 1
        data = readCM(file1);
        [~, filename1, ~] = fileparts(file1);
        filename = filename1;
    else
        data = readCM(file2);
        [~, filename2, ~] = fileparts(file2);
        filename = filename2;
    end

    data = data / 32768 / 32768 * 0.24 * 0.24; % ADC factor and attenuator
    temp = zeros(1, 64);
    matrix1 = mean(data);
    for i = 1:length(data)
        temp = temp + (matrix1 - data(i,:)).^2;
    end
    matrix2 = temp / length(data);

    % Reshape matrices
    matrix1_8x8 = reshape(matrix1, 8, 8);
    matrix2_8x8 = reshape(matrix2, 8, 8);

    % Labels
    col_labels = {'B_1', 'B_2', 'B_3', 'B_4', 'B_5', 'B_6', 'B_7', 'B_8'};
    row_labels = {'A_1', 'A_2', 'A_3', 'A_4', 'A_5', 'A_6', 'A_7', 'A_8'};

    % Create a new figure for heatmaps
    figure('Name', ['Heatmaps - ' filename], 'NumberTitle', 'off');

    % Mean heatmap
    subplot(2, 1, 1);
    h1 = heatmap(matrix1_8x8, 'ColorbarVisible', 'on');
    title(['Mean of Full Correlation (V^2) - ' filename]);
    h1.XDisplayLabels = col_labels;
    h1.YDisplayLabels = row_labels;
    h1.CellLabelFormat = '%.2e';
    colorbar;
    caxis([min(matrix1_8x8(:)) max(matrix1_8x8(:))]);
    colormap(jet);

    % MSE heatmap
    subplot(2, 1, 2);
    h2 = heatmap(matrix2_8x8, 'ColorbarVisible', 'on');
    title(['MSE of Correlation (V^4) - ' filename]);
    h2.XDisplayLabels = col_labels;
    h2.YDisplayLabels = row_labels;
    h2.CellLabelFormat = '%.2e';
    colorbar;
    caxis([min(matrix2_8x8(:)) max(matrix2_8x8(:))]);
    colormap(jet);
column_data=[];
    % Extract the second column and process
    column_data = data(:, 10);

n = length(column_data);
convert_2nd_seq=[];
convert_1st_seq=[];
convert_4th_seq=[];
convert_3rd_seq=[];
    % Bin every 400 samples
    bin_size = 1;
    num_bins = floor(n / bin_size);
    binned_data = zeros(1, num_bins);


for i = 1:num_bins
    start_idx = (i-1)*bin_size + 1;
    end_idx = min(i*bin_size, n);  % Ensure end_idx doesn't exceed n
    binned_data(i) = mean(column_data(start_idx:end_idx));
end

% Clear the later cells in column_data
column_data=[];
column_data = binned_data;  % Assign binned data to column_data
n = length(column_data);     % Update n to reflect the new length

    % Preallocate arrays to improve performance
    pair_sums = zeros(1, floor(n/2));  % Adjust size as needed
    first_order_result = zeros(1, floor(n/2));
    second_order_result = zeros(1, floor(n/3));
    third_order_result = zeros(1, floor(n/4));
    fourth_order_result = zeros(1, floor(n/5));  % New array for 4th order
    cumulative_sum = 0;
    for i = 1:floor(n)

        cumulative_sum = cumulative_sum + column_data(i);

        raw_result(i) = cumulative_sum / i;
    end
    % First order filter
    cumulative_sum = 0;
    for i = 1:floor(n/2)
        pair_sums(i) = column_data(2*i-1) - column_data(2*i);
        cumulative_sum = cumulative_sum + pair_sums(i);
        convert_1st_seq(i) = pair_sums(i);
        first_order_result(i) = cumulative_sum / i;
    end

    % Reset cumulative sum
    cumulative_sum = 0;

    % Second order filter
    for i = 1:floor(n/3)
        pair_sums(i) = column_data(3*i-2) - 2*column_data(3*i-1) + column_data(3*i);
        cumulative_sum = cumulative_sum + pair_sums(i);
        convert_2nd_seq(i) = pair_sums(i);
        second_order_result(i) = cumulative_sum / i;
    end

    % Reset cumulative sum
    cumulative_sum = 0;

    % Third order filter (modified to be truly third-order)
    for i = 1:floor(n/4)
        pair_sums(i) = column_data(4*i-3) - 3*column_data(4*i-2) + 3*column_data(4*i-1) - column_data(4*i);
        cumulative_sum = cumulative_sum + pair_sums(i);
        convert_3rd_seq(i) = pair_sums(i);
        third_order_result(i) = cumulative_sum / i;
    end

    % Reset cumulative sum
    cumulative_sum = 0;

    % Fourth order filter
    for i = 1:floor(n/5)
        pair_sums(i) = column_data(5*i-4) - 4*column_data(5*i-3) + 6*column_data(5*i-2) - 4*column_data(5*i-1) + column_data(5*i);
        cumulative_sum = cumulative_sum + pair_sums(i);
        convert_4th_seq(i) = pair_sums(i);
        fourth_order_result(i) = cumulative_sum / i;
    end

    % Fourier transforms
    N = length(column_data);
    f = (0:N-1)*(fs/N);
    fft_raw = fft(column_data);
    fft_1st = fft(convert_1st_seq, N);
    fft_2nd = fft(convert_2nd_seq, N);
    fft_3rd = fft(convert_3rd_seq, N);
    fft_4th = fft(convert_4th_seq, N);  % New FFT for 4th order
    % Convert to dB
    db_raw = 10 * log10(abs(fft_raw).^2 / 1);
    db_1st = 10 * log10(abs(fft_1st).^2 / 1);
    db_2nd = 10 * log10(abs(fft_2nd).^2 / 1);
    db_3rd = 10 * log10(abs(fft_3rd).^2 / 1);
    db_4th = 10 * log10(abs(fft_4th).^2 / 1);  % New dB conversion for 4th order

    % Create a new figure for FFT plots
    figure('Name', ['Fourier Transforms (dB) - ' filename], 'NumberTitle', 'off');

    % Plot Fourier transforms in dB
    subplot(2,3,1);
    plot(f, db_raw);
    title('FFT of Raw Data');
    xlabel('Frequency (Hz)');
    ylabel('Magnitude (dB)');
    yline(-100, '--k', '-100 dB', 'LineWidth', 1.5);
    grid on;

    subplot(2,3,2);
    plot(f, db_1st);
    title('FFT of 1st Order Filtered Data');
    xlabel('Frequency (Hz)');
    ylabel('Magnitude (dB)');
    yline(-100, '--k', '-100 dB', 'LineWidth', 1.5);
    grid on;

    subplot(2,3,3);
    plot(f, db_2nd);
    title('FFT of 2nd Order Filtered Data');
    xlabel('Frequency (Hz)');
    ylabel('Magnitude (dB)');
    yline(-100, '--k', '-100 dB', 'LineWidth', 1.5);
    grid on;

    subplot(2,3,4);
    plot(f, db_3rd);
    title('FFT of 3rd Order Filtered Data');
    xlabel('Frequency (Hz)');
    ylabel('Magnitude (dB)');
    yline(-100, '--k', '-100 dB', 'LineWidth', 1.5);
    grid on;

    subplot(2,3,5);
    plot(f, db_4th);
    title('FFT of 4th Order Filtered Data');
    xlabel('Frequency (Hz)');
    ylabel('Magnitude (dB)');
    yline(-100, '--k', '-100 dB', 'LineWidth', 1.5);
    grid on;

    sgtitle(['Fourier Transforms (dB) for ' filename]);

    % Store absolute values for loglog plot
    if fileIdx == 1
        abs_raw_result1 = abs(raw_result);
        abs_first_order1 = abs(first_order_result);
        abs_second_order1 = abs(second_order_result);
        abs_third_order1 = abs(third_order_result);
        abs_fourth_order1 = abs(fourth_order_result);
    else
        abs_raw_result2 = abs(raw_result);
        abs_first_order2 = abs(first_order_result);
        abs_second_order2 = abs(second_order_result);
        abs_third_order2 = abs(third_order_result);
        abs_fourth_order2 = abs(fourth_order_result);
    end

end

column_data_t=column_data.';


convert_1st_seq_t=convert_1st_seq.';


convert_2nd_seq_t=convert_2nd_seq.';

convert_3rd_seq_t=convert_3rd_seq.';

convert_4th_seq_t=convert_4th_seq.';


% Create loglog plots
figure('Name', ['Log-Log Plot - ' filename1], 'NumberTitle', 'off');
loglog(abs_raw_result1, '.', 'DisplayName', 'Raw data');
hold on;
loglog(abs_first_order1, 'b-', 'DisplayName', '1st Order');
loglog(abs_second_order1, 'r-', 'DisplayName', '2nd Order');

title([filename1]);
xlabel('Sample Index');
ylabel('Absolute Cumulative Average');
legend('show');
grid on;

% Add a vertical line at x = 4166
xline(4166, '--k', 'DisplayName', '100 seconds');
legend('show'); % Update legend to include the new line

figure('Name', ['Log-Log Plot - ' filename2], 'NumberTitle', 'off');
loglog(abs_raw_result2, '.', 'DisplayName', 'Raw data');
hold on;
loglog(abs_first_order2, 'b-', 'DisplayName', '1st Order');
loglog(abs_second_order2, 'r-', 'DisplayName', '2nd Order');

title([filename2]);
xlabel('Sample Index');
ylabel('Absolute Cumulative Average');
legend('show');
grid on;

% Add a vertical line at x = 4166
xline(4166, '--k', 'DisplayName', '100 seconds');
legend('show'); % Update legend to include the new line

function reshapedData = readCM(filename)
% Parameters
numElementsPerArray = 64;  % Number of elements in each array
elementSize = 8;           % Size of each double element in bytes (64 bits = 8 bytes)

% Open the binary file for reading
fid = fopen(filename, 'rb');
if fid == -1
    error('Error opening file');
end

% Read the entire file
data = fread(fid, 'double');

% Close the file
fclose(fid);

% Check the size of the data
numElements = length(data);
if mod(numElements, numElementsPerArray) ~= 0
    error('The total number of elements is not a multiple of the expected array size.');
end

% Calculate the number of arrays
numArrays = numElements / numElementsPerArray;

% Reshape the data into a matrix where each row represents an array
reshapedData = reshape(data, numElementsPerArray, numArrays)'; % 2D matrix
end
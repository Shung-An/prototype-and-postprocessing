% File path
file1 = 'C:\Users\Public\Public Repos\Quantum Measurement UI\GageStreamThruGPU\electronicNoiseAfterCryoPumpOnline.bin';

% Sampling frequency
fs = 2623 / 64;

% Read data from the file
data = readCM(file1);
[~, filename, ~] = fileparts(file1);

% Normalize data
data = data / 32768 / 32768 * 0.24 * 0.24 * 10 * 10; % ADC factor and attenuator

% Create a figure for PSD plots
figure('Name', ['PSD Analysis - ' filename], 'NumberTitle', 'off', 'Position', [100, 100, 1920, 1080]);

for channel = 1:size(data, 2)
    % Plot PSD for each channel
    subplot(8, 8, channel);  % Arrange subplots in an 8x8 grid
    [Pxx, f_psd] = pwelch(data(:, channel), [], [], [], fs);
    plot(f_psd, 10 * log10(Pxx));
    title(['Channel ' num2str(channel)]);
    xlabel('Frequency (Hz)');
    ylabel('Power (dB/Hz)');
    grid on;
end

sgtitle(['PSD of Raw Data - ' filename]);  % Overall title for PSD plots

% Create a figure for Allan Deviation plots
figure('Name', ['Allan Deviation - ' filename], 'NumberTitle', 'off', 'Position', [100, 100, 1920, 1080]);

tau = logspace(log10(1 / fs), log10(size(data, 1) / (2 * fs)), 100);
for channel = 1:size(data, 2)
    % Calculate Allan Deviation for each channel
    adev = zeros(length(tau), 1);
    [~, adev] = allandev(data(:, channel), fs, tau);
    
    % Plot Allan Deviation for each channel
    subplot(8, 8, channel);  % Arrange subplots in an 8x8 grid
    loglog(tau, adev);
    title(['Channel ' num2str(channel)]);
    xlabel('Tau (s)');
    ylabel('Allan Deviation');
    grid on;
end

sgtitle(['Allan Deviation of Raw Data - ' filename]);  % Overall title for Allan Deviation plots

function reshapedData = readCM(filename)
    % Parameters
    numElementsPerArray = 64;  % Number of elements in each array

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

function [tau, adev] = allandev(y, fs, tau)
    % Calculate Allan deviation
    adev = zeros(size(tau));
    
    for i = 1:length(tau)
        n = floor(tau(i) * fs);
        if n == 0
            continue;
        end
        
        % Compute the overlapping Allan variance
        y_chunked = reshape(y(1:floor(length(y) / n) * n), n, []);
        y_mean = mean(y_chunked, 1);
        adev(i) = sqrt(sum(diff(y_mean).^2) / (2 * (length(y_mean) - 1))) / tau(i);
    end
end

% GPUplot Script - Process and plot FFT of data using GPU in three subplots

% Parameters
fs = 655780838; % Sampling rate in Hz (replace with your actual sampling rate)
f_min = 0;   % Minimum frequency for plotting in Hz
f_max = 82e6;   % Maximum frequency for plotting in Hz

% Assuming 'data' is a 2xN matrix containing two channels of data
% Replace with your actual data
% data = [channel1_data; channel2_data];

% Ensure data has two channels
assert(size(data, 1) == 2, 'Data must have two channels.');

% Length of data
N = size(data, 2);

% Compute frequency axis
f = fs * (0:N-1) / N;

% Find indices for f_min to f_max
indices = (f >= f_min) & (f <= f_max);
f_plot = f(indices) / 1E6; % Convert to MHz for plotting

% Transfer data to GPU and perform FFT
data_gpu = gpuArray(data);
fft_data_gpu = fft(data_gpu, [], 2);
fft_data = gather(fft_data_gpu);

% Compute cross-channel product on GPU
AxB_gpu = prod(data_gpu, 1);
fft_channelx_gpu = fft(AxB_gpu);
fft_channelx = gather(fft_channelx_gpu);

% Scaling factor
scaling_factor = 1/N;

% Convert magnitude to dB
fft_channel1_dB = 20 * log10(abs(fft_data(1, :)) * scaling_factor);
fft_channel2_dB = 20 * log10(abs(fft_data(2, :)) * scaling_factor);
fft_channelx_dB = 20 * log10(abs(fft_channelx) * scaling_factor);

% Create figure and subplots without displaying it
figure('Visible', 'off', 'Position', [100, 100, 1920, 1200]); % Set dimensions

% Subplot for Channel 1
subplot(3, 1, 1);
plot(f_plot, fft_channel1_dB(indices), 'LineWidth', 1);
xlabel('Frequency (MHz)');
ylabel('Magnitude [dB]');
title('Channel 1 Frequency Domain');
grid on;
xlim([f_min, f_max] / 1E6);
xline(40, '--r', 'LineWidth', 0.5); % Add vertical line at 40 MHz
yline(-150, '--b', 'LineWidth', 0.5); % Add first horizontal line at -20 dB
yline(-125, '--b', 'LineWidth', 0.5); % Add second horizontal line at -40 dB
yline(-100, '--b', 'LineWidth', 0.5); % Add third horizontal line at -60 dB

% Subplot for Channel 2
subplot(3, 1, 2);
plot(f_plot, fft_channel2_dB(indices), 'LineWidth', 1);
xlabel('Frequency (MHz)');
ylabel('Magnitude [dB]');
title('Channel 2 Frequency Domain');
grid on;
xlim([f_min, f_max] / 1E6);
xline(40, '--r', 'LineWidth', 0.5); % Add vertical line at 40 MHz
yline(-150, '--b', 'LineWidth', 0.5); % Add first horizontal line at -20 dB
yline(-125, '--b', 'LineWidth', 0.5); % Add second horizontal line at -40 dB
yline(-100, '--b', 'LineWidth', 0.5); % Add third horizontal line at -60 dB

% Subplot for Cross Channel
subplot(3, 1, 3);
plot(f_plot, fft_channelx_dB(indices), 'LineWidth', 1, 'Color', 'g');
xlabel('Frequency (MHz)');
ylabel('Magnitude [dB]');
title('Cross Channel Frequency Domain');
grid on;
xlim([f_min, f_max] / 1E6);
xline(40, '--r', 'LineWidth', 0.5); % Add vertical line at 40 MHz
yline(-150, '--b', 'LineWidth', 0.5); % Add first horizontal line at -20 dB
yline(-125, '--b', 'LineWidth', 0.5); % Add second horizontal line at -40 dB
yline(-100, '--b', 'LineWidth', 0.5); % Add third horizontal line at -60 dB

% Overall title for the figure
sgtitle('Frequency Domain Representation (dB)');

% Create subfolder if it doesn't exist
outputFolder = 'FFT spectrum';
if ~exist(outputFolder, 'dir')
    mkdir(outputFolder);
end

% Get current time for filename
currentTime = datetime('now');
formattedTime = datestr(currentTime, 'yyyy-mm-dd_HH-MM-SS'); % Format time

% Save the figure with the current time in the filename at high resolution
filename = fullfile(outputFolder, ['FFT_spectrum_' formattedTime '.png']);
exportgraphics(gcf, filename, 'Resolution', 300); % Set resolution to 300 DPI

% Optionally, close the figure to free up memory
close(gcf);
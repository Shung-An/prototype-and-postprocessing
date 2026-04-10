clear;
% Specify the file path
file_path = 'C:\Program Files (x86)\Gage\CompuScope\CompuScope C SDK\C Samples\GageAcquire\Win32\Debug\Acquire_CH1.txt';
data = readmatrix(file_path, 'NumHeaderLines', 12);
% Open the file for reading
outputdata = reshape(data, 12, 680000);
sampleRate = 1E9;
bufferSize = 8160000;
% data is a 2xN matrix, where N is the number of data pairs
%%
% Extract x and y coordinates
x = data;

% ... (previous code remains unchanged)

% Define the subfolder for saving plots
saveFolder = 'Plots';

% Check if the subfolder exists, create it if not
if ~exist(saveFolder, 'dir')
    mkdir(saveFolder);
end
%%
% Generate a serial filename based on the current date and time
currentTime = datetime('now', 'Format', 'yyyyMMdd_HHmmss');
saveFilename = fullfile(saveFolder, ['plot_' char(currentTime) '.png']);

% Create a new figure (invisible) for saving


% Plot the data in the invisible figure
hFig = figure('Visible', 'off');

hold on;

for i = 1:680
    plot(outputdata(:, i),'o', 'DisplayName', sprintf('Row %d', i));
end
% Save the invisible figure as an image file
grid on;

saveas(hFig, saveFilename);

% Close the invisible figure
close(hFig);

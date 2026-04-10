
% Specify the file path



% Assuming you have already read the data using the previous code snippet
% data is a 2xN matrix, where N is the number of data pairs
%%
% Extract x and y coordinates
x = data(1, :);
if (size(data,1)==2)
    y = data(2, :);
end
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
hFig = figure('Visible', 'off');

% Plot the data in the invisible figure
plot(x, 'LineWidth', 3, 'DisplayName', 'Ch1');
hold on;
if (size(data,1)==2)
    plot(y,  'LineWidth', 1, 'DisplayName', 'Ch2');
end
title(['Buffer size (Samples) = ']);
xlabel(['Samples ']);

% xlabel(['k']);

ylabel('Voltage Amplitude(V)');

% ylabel('Correlated Amplitude (unconvert)');

legend('show');
grid on;

% Save the invisible figure as an image file
saveas(hFig, saveFilename);

% Close the invisible figure
close(hFig);
% X=fft(x);
% plot(1000/length(x)*(0:length(x)-1),abs(X),"LineWidth",3)
% title("Complex Magnitude of fft Spectrum")
% xlabel("f (Hz)")
% ylabel("|fft(X)|")

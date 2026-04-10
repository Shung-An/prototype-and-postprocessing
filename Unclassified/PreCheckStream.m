clear;
% Specify the file path
file_path = 'C:\Program Files (x86)\Gage\CompuScope\CompuScope C SDK\C Samples\Advanced\GageStreamThruGPU-Modified\x64\Debug\Analysis.txt';

% Open the file for reading
fid = fopen(file_path, 'r');

% Check if the file opened successfully
if fid == -1
    error('Error opening the file.');
end

try
    % Read the header line (Data%d)
    bufferSize = fscanf(fid, 'Buffer size (Samples)\n%d\n', 1);
    sampleRate = fscanf(fid, 'Sampling Rate (Hz)\n%d\n', 1);

    % Read the data pairs using the specified format
    data = fscanf(fid, '%d\t%d\t%d\n', [3, Inf]);

    % Close the file
    fclose(fid);



    % Now you can use the 'data' variable for further processing or analysis
catch
    % Close the file in case of an error
    fclose(fid);
    error('Error reading data from the file.');
end
% Assuming you have already read the data using the previous code snippet
% data is a 2xN matrix, where N is the number of data pairs
%%
% Extract x and y coordinates
x = data(2, 2:end-4);
sumGPU = sum(x);
correlationGPUinV2 = sumGPU / length(x)/bufferSize;
if (size(data,1)==3)
    y = data(3, 2:end-4)/ 32768 * 0.24 / 32768 * 0.24;
    sumCPU = sum(y);
    correlationCPUinV2 = sumCPU / length(y)/bufferSize;
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
plot(x, 'LineWidth', 3, 'DisplayName', 'GPU');
hold on;
if (size(data,1)==3)
    plot(y,  'LineWidth', 1, 'DisplayName', 'CPU');
end
title(['Buffer size (Samples) = ' num2str(bufferSize)]);
xlabel(['Time (' num2str(1/sampleRate*bufferSize) ' s/div)']);

% xlabel(['k']);

ylabel('Correlated sum(V^2)');

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


% Specify the file path
file_path = 'C:\Program Files (x86)\Gage\CompuScope\CompuScope C SDK\Test\Analysis.txt';

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
    data = fscanf(fid, '%d\t%d\n', [2, Inf]);

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
% index = find(data(2,:) == data(3,:), 1, 'first');
% Extract x and y coordinates

x = data(2, 2:end)/ 32768 * 0.24 / 32768 * 0.24;
sumGPU = sum(x);
correlationGPUinV2 = sumGPU / length(x)/bufferSize;

if (size(data,1)==3)
    y = data(3, 2:end)/ 32768 * 0.24 / 32768 * 0.24;
    sumCPU = sum(y);
    correlationCPUinV2 = sumCPU / length(y)/bufferSize;
end
% xa = data(2, :)/ 32768 * 0.24 / 32768 * 0.24;
% ya = data(3, :)/ 32768 * 0.24 / 32768 * 0.24;




% ... (previous code remains unchanged)

% Define the subfolder for saving plots
saveFolder = 'Plots';

% Check if the subfolder exists, create it if not
if ~exist(saveFolder, 'dir')
    mkdir(saveFolder);
end

% Generate a serial filename based on the current date and time
currentTime = datetime('now', 'Format', 'yyyyMMdd_HHmmss');
saveFilename = fullfile(saveFolder, ['plot_' char(currentTime) '.png']);

% Create a new figure (invisible) for saving
hFig = figure('Visible', 'off');

% Plot the data in the invisible figure
plot(x, 'o-', 'LineWidth', 3, 'DisplayName', ['GPU = ' num2str(correlationGPUinV2)]);
hold on;
if (size(data,1)==3)
    plot(y, '*-', 'LineWidth', 2, 'DisplayName', ['CPU = ' num2str(correlationCPUinV2)]);
end
title(['Buffer size (Samples) = ' num2str(bufferSize)],['Sample Rate (GHz) = ' num2str(sampleRate/1E+9) '; ToTal Ns (GS) = ' num2str(bufferSize*(length(x)-2)/1E+9)]);
xlabel('Buffer Packages (Counts, Timestamp)');
ylabel('Summation of Correlation Amplitude (V^2)');
legend('show');
grid on;

% Save the invisible figure as an image file
saveas(hFig, saveFilename);

% Close the invisible figure
close(hFig);
% disp(['Miss ' num2str(index - 1) ' elements']);

noise = [1:6];
noise (1) = sum(x(1))/1/bufferSize;
noise (2) = sum(x(1:10))/10/bufferSize;
noise (3) = sum(x(1:100))/100/bufferSize;
if length(x)>1000
noise (4) = sum(x(1:1000))/1000/bufferSize;
end
if length(x)>10000
noise (5) = sum(x(1:10000))/10000/bufferSize;
end
if length(x)>100000
noise (6) = sum(x(1:100000))/100000/bufferSize;
end

filename = 'noise_data.txt';
fid = fopen(filename, 'a');
fprintf(fid,'%s\t',char(currentTime));
fprintf(fid, '%e\t',noise);
fprintf(fid, '\n');
fclose(fid);
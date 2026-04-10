% Open the file
fileID = fopen('C:\Users\jr151\source\repos\Quantum Measurement UI\results\20241121_104643\.txt', 'r');
% Open the file


% Skip the first 6 rows
for i = 1:6
    fgetl(fileID);
end

% Initialize arrays to store the data
rowIndex = [];
timeStamp = {};
measurements = [];

% Read the rest of the file line by line
while ~feof(fileID)
    line = fgetl(fileID);
    if ~isempty(line)
        % Split the line by tabs
        rowData = strsplit(line, '\t');
        
        % Extract row index (first element)
        rowIndex = [rowIndex; str2double(rowData{1})];
        
        % Extract timestamp (second element)
        timeStamp{end+1} = rowData{2};
        
        % Extract measurements (remaining elements)
        measurementRow = str2double(rowData(3:end));
        measurements = [measurements; measurementRow];
    end
end

% Close the file
fclose(fileID);

% Convert timeStamp cell array to a string array
timeStamp = string(timeStamp);

% Verify the size of measurements
[rows, cols] = size(measurements);
% After reading the data
[rows, cols] = size(measurements);
if cols ~= 64
    warning('The number of measurement columns is %d, expected 64.', cols);
    % Handle the extra column
    if cols == 65
        measurements = measurements(:, 1:64); % Keep only the first 64 columns
        disp('Removed the extra column.');
    else
        error('Unexpected number of columns. Please check your data.');
    end
end
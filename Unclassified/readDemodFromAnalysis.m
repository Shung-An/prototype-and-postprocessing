clear;
% Define file path
file_path = 'C:/Program Files (x86)/Gage/CompuScope/CompuScope C SDK/Test/Analysis.txt'; % Replace 'your_file.txt' with the path to your file

% Open the file for reading
fid = fopen(file_path, 'r');

% Initialize variables to store data
data = [];
buffer_sizes = [];
sampling_rates = [];

% Read the file line by line
tline = fgetl(fid);
while ischar(tline)
    % Check for lines containing Buffer size
    if startsWith(tline, 'Buffer size (Samples)')
        % Read the next line containing buffer size value
        buffer_size = str2double(fgetl(fid));
        buffer_sizes(end+1) = buffer_size;
    % Check for lines containing Sampling Rate
    elseif startsWith(tline, 'Sampling Rate (Hz)')
        % Read the next line containing sampling rate value
        sampling_rate = str2double(fgetl(fid));
        sampling_rates(end+1) = sampling_rate;
    % Check for lines containing numeric data
    elseif ~startsWith(tline, '///')

        % Split the line by tab delimiter and skip the first element (index)
        numeric_data = cell2mat(textscan(tline, '%*f %f'));
        data = [data; numeric_data];
    end
    
    % Read the next line
    tline = fgetl(fid);
end

% Close the file
fclose(fid);
data=data/ 32768 * 0.24 / 32768 * 0.24;
sum(data)/length(data)/(buffer_size/2);
for i=1:length(data)
    noiseEvents(i,2)=sum(data(1:i))/i/(buffer_size/2);
    noiseEvents(i,1)=i*(buffer_size/2);
end 
x=noiseEvents(:,1);
y=noiseEvents(:,2);
plot(x,y);
loglog(x,abs(y));
hold on;
% Define the range of x values for the function y = 1/sqrt(x)
x_function = logspace(7, 12, 100);
y_function = 1 ./ sqrt(x_function)./100000000;

% Plot both the dataset and the function on log-log scale
loglog(x_function, y_function, 'LineWidth', 2); % Plot the function

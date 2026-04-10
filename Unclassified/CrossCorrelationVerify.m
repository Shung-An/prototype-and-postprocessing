%% Data Preprocessing and Correlation Analysis
% This script loads and processes binary half-precision data

% Define the number of bytes to read
num_bytes_to_read = 64045056;  % 64,045,056 bytes
num_elements = num_bytes_to_read / 2;  % each 'half' is 2 bytes

% Load the first 64,045,056 bytes of binary data from data.dat
fileID = fopen('C:\\Users\\jr151\\GageData\\data.dat', 'r');
data_uint16 = fread(fileID, [1, num_elements], 'int16');  % Reading as uint16
fclose(fileID);

% Convert to half-precision
data_half = half(data_uint16);

% Print the first 10 elements of data_half
disp('First 10 elements of data_half:');
disp(data_half(1:10));

% Convert to double for processing
data_double = double(data_half);

%% Reshape the data into two rows
A = data_double(1:2:end);  % Select elements at odd positions
B = data_double(2:2:end);  % Select elements at even positions

% Ensure we only take the first 16,011,264 elements for each row
A = A(1:16011264);
B = B(1:16011264);

% Combine into a two-row matrix
data_reshaped = [A; B];

% Display the shape of the reshaped data
disp('Shape of data_reshaped:');
disp(size(data_reshaped));  % Should display [2, 16011264]

% Now you can proceed with further processing of data_reshaped

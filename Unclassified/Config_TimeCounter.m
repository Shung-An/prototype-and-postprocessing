clear;
% Input the new value for TimeCounter
newTimeCounterValue = input('Enter the new value for TimeCounter (s): ');
newTimeCounterValue = newTimeCounterValue*1000;
% Read the content of the text file
filePath = 'C:/Program Files (x86)/Gage/CompuScope/CompuScope C SDK/Test/StreamThruGPU.ini';  % Replace with the actual path
fileID = fopen(filePath, 'r+');  % Open for reading and writing
% Create a regular expression pattern for the line containing TimeCounter
pattern = 'TimeCounter=';  % Adjust pattern to match your file structure

% Read the content and find the line containing TimeCounter
content = fread(fileID, '*char').';
startIndex = regexp(content, pattern, 'start');

% Check if the pattern was found
if isempty(startIndex)
    disp('Pattern not found in the file.');
    fclose(fileID);
    return;
end

% Move the file position to the start of the line
fseek(fileID, startIndex(1), 'bof');
% Calculate the end index of the line
endIndex = regexp(content, pattern, 'end');
% Replace the line with the new value

fprintf(fileID, '                 ');
fseek(fileID, startIndex(1), 'bof');
fprintf(fileID, 'imeCounter=%d',newTimeCounterValue);
fclose(fileID);
disp('Replacement completed.');

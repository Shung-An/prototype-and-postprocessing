function reshapedData =  readCM(filePath)
    % Parameters
    numElementsPerArray = 64;  % Number of elements in each array
    elementSize = 8;           % Size of each double element in bytes (64 bits = 8 bytes)
    
    % Open the binary file for reading
    fid = fopen(filePath, 'rb');
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

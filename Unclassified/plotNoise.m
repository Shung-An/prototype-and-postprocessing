file_path = 'C:\Program Files (x86)\Gage\CompuScope\CompuScope C SDK\Test\noise_data.txt';
fid = fopen(file_path, 'r');

% Check if the file opened successfully
if fid == -1
    error('Error opening the file.');
end

try

    % Read the data pairs using the specified format
    data = fscanf(fid, '%*s\t%e\t%e\t%e\t%e\t%e\t%e\n',[6,inf]);

    % Close the file
    fclose(fid);

    % Now you can use the 'data' variable for further processing or analysis
catch
    % Close the file in case of an error
    fclose(fid);
    error('Error reading data from the file.');
end

% Plot each column of the dataMatrix
figure;

for col = 1:size(data, 2)
    plot(data(:, col), 'DisplayName', sprintf('Column %d', col));
    hold on;
end

% Add labels and legend
xlabel('10^{n-1}');
ylabel('Correlated Amplitude (V^2)');
title('Plot of Columns');
legend('show');

% Display the plot
hold off;
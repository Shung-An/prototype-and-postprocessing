clear;
file_path = 'C:/Program Files (x86)/Gage/CompuScope/CompuScope C SDK/Test/demodulateData.txt';

% Open the file
fid = fopen(file_path, 'r');

% Check if the file opened successfully
if fid == -1
    error('Error opening the file.');
end

try
    % Read the data using fscanf
    data = fscanf(fid, '%*s\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\t%e\n', [99, inf]);

    % Close the file
    fclose(fid);
x=2:100;
    % Plot each column of the data
    figure;
    for col = 1:size(data, 2)
        plot(x,data(:, col), '*', 'DisplayName', sprintf('Column %d', col));
        hold on;
    end

    % Add labels and legend
    xlabel('Index');
    ylabel('Correlated Amplitude (V^2)');
    title('Plot of Columns');
    legend('show');
    
    % Display the plot
    hold off;

catch
    % Close the file in case of an error
    fclose(fid);
    error('Error reading data from the file.');
end
ss = randi([0,100],1,99);

for i=1:99
ss(i)=sum(data(i,:))/103;
end

plot (x, ss,'*');
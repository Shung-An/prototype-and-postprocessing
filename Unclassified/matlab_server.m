% Create TCP/IP server
server = tcpip('0.0.0.0', 8081, 'NetworkRole', 'server');
fopen(server);

disp('MATLAB server is running. Waiting for client connection...');

try
    % Prepare figure for visualization
    figure;
    
    while true
        if server.BytesAvailable > 0
            data = fread(server, server.BytesAvailable, 'char');
            message = char(data');
            disp(['Received from client: ', message]);
            data(length(data))=[];
            
            % Convert received string to datetime
            currentTime = datetime(message, 'InputFormat', 'eee MMM dd HH:mm:ss yyyy');
            
            % Plot the current time in a simple visualization
            plot(datetime('now'), rand(), 'o'); % Random y-value for demonstration
            xlabel('Time');
            ylabel('Random Value');
            title('Current Time Visualization');
            drawnow; % Update the plot
            
            pause(1); % Adjust pause as needed
        end
        pause(0.1); % Small delay to prevent busy-waiting
    end
catch ME
    disp(['Error: ', ME.message]);
end

% Clean up
fclose(server);
delete(server);
clear server;
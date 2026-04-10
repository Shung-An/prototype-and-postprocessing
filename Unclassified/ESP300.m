% Create a serialport object
s = serialport("COM1", 19200, "Timeout", 1);

% Configure the terminator
configureTerminator(s, "CR/LF");

try
    % Enable motor
    sendCommand(s, '1MO');
    pause(0.5); % Wait for motor to fully enable

    % Set acceleration and velocity limits
    sendCommand(s, '1AC2'); % Set acceleration to 2 units/s^2
    sendCommand(s, '1AG2'); % Set deceleration to 2 units/s^2
    sendCommand(s, '1VA10'); % Set velocity to 10 units/s

    while true
        % Get user input for target position
        targetPosition = input('Enter target position (or ''q'' to quit): ');
        
        % Check if user wants to quit
        if ischar(targetPosition) && targetPosition == 'q'
            break;
        end
        
        % Move axis 1 to the target position
        sendCommand(s, ['1PA' num2str(targetPosition)]);
        fprintf('Moving to position: %d\n', targetPosition);
        
        % Wait for the movement to complete
        isMoving = true;
        while isMoving
            % Get current position of axis 1
            position = sendCommand(s, '1TP');
            currentPosition = str2double(position);
            
            % Display current position
            fprintf('Current position: %.2f\n', currentPosition);
            
            % Check if the movement is complete
            motionStatus = sendCommand(s, '1MD');
            isMoving = ~contains(motionStatus, '0');
            
            % Add a small pause to reduce CPU usage
            pause(0.1);
        end
        
        fprintf('Reached target position.\n\n');
    end

catch exception
    fprintf('An error occurred: %s\n', exception.message);
end

% Close the serial port when done
clear s;

% Function to send command and read response
function response = sendCommand(s, command)
    writeline(s, command);
    response = readline(s);
end
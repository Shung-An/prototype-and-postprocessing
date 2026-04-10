function picomotorFeedbackLoop()
    % Initialize the Data Acquisition
    d = daqlist("ni");
    deviceInfo = d{1, "DeviceInfo"};
    dq = daq("ni");
    dq.Rate = 250000;  % Set the sampling rate

    % Add input channels for ai0 to ai3
    for ch = 0:3
        addinput(dq, "Dev1", sprintf('ai%d', ch), "Voltage");
    end

    % Initialize the Picomotor
    USBADDR = 1; % Set in the menu of the device, only relevant if multiple are attached
    try
        NPasm = NET.addAssembly('C:\Program Files\New Focus\New Focus Picomotor Application\Samples\UsbDllWrap.dll');
        NPASMtype = NPasm.AssemblyHandle.GetType('Newport.USBComm.USB');
        NP_USB = System.Activator.CreateInstance(NPASMtype);
        NP_USB.OpenDevices();
        
        % Query device information
        querydata = System.Text.StringBuilder(64);
        NP_USB.Query(USBADDR, '*IDN?', querydata);
        devInfo = char(ToString(querydata));
        fprintf(['Device attached is ' devInfo '\n']);
    catch ME
        fprintf('Error initializing Picomotor: %s\n', ME.message);
        return;  % Exit the function if initialization fails
    end

    % Define the motor control channels and tolerance
    motor1Channels = [1, 2];  % Channels ai0 and ai1 control motor 1
    motor2Channels = [3, 4];  % Channels ai2 and ai3 control motor 2
    tolerance = 0.0001;    % Acceptable voltage difference (e.g., 0.001V)

    % Set up the figure for real-time plotting with subplots
    hFig = figure('Name', 'Real-Time Data Acquisition', 'NumberTitle', 'off', 'Position', [100, 100, 1000, 600]);
    hAx1 = subplot(2,1,1, 'Parent', hFig);
    hold(hAx1, 'on');
    hAx2 = subplot(2,1,2, 'Parent', hFig);
    hold(hAx2, 'on');

    % Initialize text objects for displaying differences and power
    hDiffText1 = annotation('textbox', [0.68, 0.91, 0.18, 0.05], 'String', 'Diff (Ch0-Ch1): 0 V', 'EdgeColor', 'none');
    hDiffText2 = annotation('textbox', [0.68, 0.44, 0.18, 0.05], 'String', 'Diff (Ch2-Ch3): 0 V', 'EdgeColor', 'none');
    hPowerText1 = annotation('textbox', [0.84, 0.91, 0.18, 0.05], 'String', '0 mW; 0 mW', 'EdgeColor', 'none');
    hPowerText2 = annotation('textbox', [0.84, 0.44, 0.18, 0.05], 'String', '0 mW; 0 mW', 'EdgeColor', 'none');

    % Initialize line objects for each channel
    hLines = gobjects(4, 1);
    colors = lines(4);  % Get distinct colors for the plots

    % Plot channels 0 and 1 in the first subplot
    hLines(1) = plot(hAx1, NaN, NaN, 'DisplayName', 'Channel ai0', 'Color', colors(1, :));
    hLines(2) = plot(hAx1, NaN, NaN, 'DisplayName', 'Channel ai1', 'Color', colors(2, :));

    % Plot channels 2 and 3 in the second subplot
    hLines(3) = plot(hAx2, NaN, NaN, 'DisplayName', 'Channel ai2', 'Color', colors(3, :));
    hLines(4) = plot(hAx2, NaN, NaN, 'DisplayName', 'Channel ai3', 'Color', colors(4, :));

    xlabel(hAx1, 'Time (s)');
    ylabel(hAx1, 'Voltage (V)');
    title(hAx1, 'Channels 0 and 1');
    legend(hAx1, 'show');

    xlabel(hAx2, 'Time (s)');
    ylabel(hAx2, 'Voltage (V)');
    title(hAx2, 'Channels 2 and 3');
    legend(hAx2, 'show');

    % Set the duration for each read
    readDuration = seconds(0.001);

    % Create buffers for the data
    dataBuffer = [];
    timeBuffer = [];
    maxBufferSize = 0.001 * dq.Rate;  % Keep 1 millisecond of data

    % Set the time range for plotting (0 to 0.001 seconds)
    plotTimeRange = [0, 0.001];

    % Initialize horizontal grid lines
    hGridLines = gobjects(4, 1);
    for i = 1:2
        hGridLines(i) = line(hAx1, plotTimeRange, [0 0], 'Color', [0.7 0.7 0.7], 'LineStyle', '--');
    end
    for i = 3:4
        hGridLines(i) = line(hAx2, plotTimeRange, [0 0], 'Color', [0.7 0.7 0.7], 'LineStyle', '--');
    end

    % Start the feedback loop
    while ishandle(hFig)
        % Read data for the specified duration
        data = read(dq, readDuration, "OutputFormat", "Matrix");
        timestamps = (0:size(data,1)-1)' / dq.Rate;

        % Update the data buffer
        dataBuffer = [dataBuffer; data];
        timeBuffer = [timeBuffer; timestamps + (length(timeBuffer)/dq.Rate)];

        % Trim the buffer to the maximum size
        if length(dataBuffer) > maxBufferSize
            dataBuffer = dataBuffer(end-maxBufferSize+1:end, :);
            timeBuffer = timeBuffer(end-maxBufferSize+1:end);
        end

        % Calculate the mean for each channel
        averagedData = mean(dataBuffer);

        % Update the plot for all channels (live data)
        for i = 1:4
            set(hLines(i), 'XData', timeBuffer, 'YData', dataBuffer(:, i));
        end

        % Update horizontal grid lines
        for i = 1:4
            set(hGridLines(i), 'YData', [averagedData(i) averagedData(i)]);
        end

        % Set the x-axis limits to the desired range
        xlim(hAx1, plotTimeRange + timeBuffer(end) - 0.001);
        xlim(hAx2, plotTimeRange + timeBuffer(end) - 0.001);

        % Auto-tune the y-axis scale based on the live data
        ylim(hAx1, [min(min(dataBuffer(:, [1, 2]))), max(max(dataBuffer(:, [1, 2])))]);
        ylim(hAx2, [min(min(dataBuffer(:, [3, 4]))), max(max(dataBuffer(:, [3, 4])))]);

        % Calculate and display differences
        diff1 = averagedData(1) - averagedData(2);  % Ch0 - Ch1
        diff2 = averagedData(3) - averagedData(4);  % Ch2 - Ch3
        power0 = averagedData(1)/10;
        power1 = averagedData(2)/10;
        power2 = averagedData(3)/10;
        power3 = averagedData(4)/10;

        set(hDiffText1, 'String', sprintf('Diff (Ch0-Ch1): %.3f V', diff1));
        set(hDiffText2, 'String', sprintf('Diff (Ch2-Ch3): %.3f V', diff2));
        set(hPowerText1, 'String', sprintf('%.3f mW; %.3f mW', power0, power1));
        set(hPowerText2, 'String', sprintf('%.3f mW; %.3f mW', power2, power3));

        % Update titles with current motor positions
        title(hAx1, sprintf('Channels 0 and 1 (Motor 1) - Position: %.2f', getCurrentPosition(1, NP_USB, USBADDR)));
        title(hAx2, sprintf('Channels 2 and 3 (Motor 2) - Position: %.2f', getCurrentPosition(2, NP_USB, USBADDR)));

        drawnow;

        % Perform feedback adjustment for motor 1 and motor 2
        feedbackLoop(averagedData, motor1Channels, 1, tolerance, NP_USB, USBADDR);
        feedbackLoop(averagedData, motor2Channels, 2, tolerance, NP_USB, USBADDR);
    end
end

function feedbackLoop(currentValues, motorChannels, motorNumber, tolerance, NP_USB, USBADDR)
    % Calculate the difference between the two channels for this motor
    difference = currentValues(motorChannels(1)) - currentValues(motorChannels(2));

    % Check if the difference exceeds the tolerance
    if abs(difference) > tolerance
        % Determine adjustment direction and amount
        adjustmentDirection = sign(difference);
        adjustmentAmount = difference * 50;  % Convert to picomotor units (e.g., 10 steps per volt)
        command = sprintf('%d%s%d', motorNumber, 'PR-', round(adjustmentAmount));
        NP_USB.Write(USBADDR, command); % Send the command to move the picomotor
        fprintf('Sent command to motor %d: %s\n', motorNumber, command);  % Log the command for debugging
    end
end


function position = getCurrentPosition(motorNumber, NP_USB, USBADDR)
    % Query the current position of the specified motor
    querydata = System.Text.StringBuilder(64);
    NP_USB.Query(USBADDR, sprintf('%dTP?', motorNumber), querydata);
    position = str2double(char(ToString(querydata)));
end
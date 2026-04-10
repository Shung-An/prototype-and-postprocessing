function realtimeMonitor()
    % Initialize the Data Acquisition
    d = daqlist("ni");
    deviceInfo = d{1, "DeviceInfo"};
    dq = daq("ni");
    dq.Rate = 250000;  % Set the sampling rate

    % Add input channels for ai0 to ai3
    for ch = 0:3
        addinput(dq, "Dev1", sprintf('ai%d', ch), "Voltage");
    end

    % Set up the figure for real-time plotting with subplots
    hFig = figure('Name', 'Real-Time Data Acquisition', 'NumberTitle', 'off');
    hAx1 = subplot(2,1,1, 'Parent', hFig);
    hold(hAx1, 'on');
    hAx2 = subplot(2,1,2, 'Parent', hFig);
    hold(hAx2, 'on');

    % Initialize line objects for each channel
    hLines = gobjects(4, 1);
    colors = lines(4);  % Get distinct colors for the plots

    % Plot channels 0 and 3 in the first subplot
    hLines(1) = plot(hAx1, NaN, NaN, 'DisplayName', 'Channel ai0', 'Color', colors(1, :));
    hLines(2) = plot(hAx1, NaN, NaN, 'DisplayName', 'Channel ai3', 'Color', colors(2, :));

    % Plot channels 1 and 2 in the second subplot
    hLines(3) = plot(hAx2, NaN, NaN, 'DisplayName', 'Channel ai1', 'Color', colors(3, :));
    hLines(4) = plot(hAx2, NaN, NaN, 'DisplayName', 'Channel ai2', 'Color', colors(4, :));

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
    maxBufferSize = 0.001 * dq.Rate;  % Keep 10 seconds of data

    % Continuously acquire and plot data
    while ishandle(hFig)
        % Read data for the specified duration
        data = read(dq, readDuration, "OutputFormat", "Matrix");
        timestamps = (0:length(data)-1)' / dq.Rate;

        % Update the data buffer
        dataBuffer = [dataBuffer; data];
        timeBuffer = [timeBuffer; timestamps + (length(timeBuffer)/dq.Rate)];

        % Trim the buffer to the maximum size
        if length(dataBuffer) > maxBufferSize
            dataBuffer = dataBuffer(end-maxBufferSize+1:end, :);
            timeBuffer = timeBuffer(end-maxBufferSize+1:end, :);
        end

        % Update the plot for channels 0 and 3
        set(hLines(1), 'XData', timeBuffer, 'YData', dataBuffer(:, 1));
        set(hLines(2), 'XData', timeBuffer, 'YData', dataBuffer(:, 2));

        % Update the plot for channels 1 and 2
        set(hLines(3), 'XData', timeBuffer, 'YData', dataBuffer(:, 3));
        set(hLines(4), 'XData', timeBuffer, 'YData', dataBuffer(:, 4));

        % Auto-tune the y-axis scale based on the data
        ylim(hAx1, [min(min(dataBuffer(:, [1, 2]))), max(max(dataBuffer(:, [1, 2])))]);
        ylim(hAx2, [min(min(dataBuffer(:, [3, 4]))), max(max(dataBuffer(:, [3, 4])))]);

        drawnow;
    end

    % Save the acquired data to a file when the figure is closed
    save('acquiredData.mat', 'timeBuffer', 'dataBuffer');
end

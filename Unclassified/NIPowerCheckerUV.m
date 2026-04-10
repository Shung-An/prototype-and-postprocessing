function NIPowerCheckerUV()
    % Initialize the Data Acquisition
    d = daqlist("ni");
    deviceInfo = d{1, "DeviceInfo"};
    dq = daq("ni");
    dq.Rate = 250000;  % Set the sampling rate

    % Add input channel for ai4 (channel 5)
    addinput(dq, "Dev1", 'ai0', "Voltage");

    % Create main figure with tab group
    hFig = figure('Name', 'NI Power Checker (Ch5) with 1ms Stats Update', ...
                 'NumberTitle', 'off', ...
                 'Position', [100, 100, 1400, 800]);
    
    % Create tab group
    tabGroup = uitabgroup('Parent', hFig);
    
    %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
    % FIRST TAB: PLOTS AND HISTOGRAMS WITH REAL-TIME STATS
    %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
    plotsTab = uitab('Parent', tabGroup, 'Title', 'Plots & Stats');
    
    % Create a 2x1 grid of subplots in the first tab
    % Top: Time series plot
    hAx1 = subplot(2,1,1, 'Parent', plotsTab);
    hold(hAx1, 'on');
    
    % Bottom: Histogram
    hAx2 = subplot(2,1,2, 'Parent', plotsTab);

    % Set fixed Y-axis limits for time series plot with units
    ylim(hAx1, [0 1]);
    ylabel(hAx1, 'Voltage (V)');
    xlabel(hAx1, 'Time (s)');
        
    % Set grid for time series
    grid(hAx1, 'on');
    grid(hAx2, 'on');

    % Initialize line object for channel 5
    hLine = plot(hAx1, NaN, NaN, 'DisplayName', 'Ch5', ...
                'Color', [0 0.4470 0.7410], 'LineWidth', 1.5);
                
    % Add real-time stats annotation for Ch5
    hStatsText = annotation(plotsTab, 'textbox', [0.15 0.85 0.2 0.1], ...
                         'String', '', 'EdgeColor', 'none', ...
                         'FontSize', 10, 'FontWeight', 'bold', ...
                         'BackgroundColor', [1 1 1 0.7]);

    % Initialize histogram object with units
    histEdges = linspace(0, 1, 199); % Adjust bin edges as needed
    
    % Create histogram for channel 5 with stats box
    hHist = histogram(hAx2, NaN, 'BinEdges', histEdges, 'FaceColor', [0 0.4470 0.7410]);
    title(hAx2, 'Ch5 Distribution (All Data)');
    xlabel(hAx2, 'Voltage (V)');
    ylabel(hAx2, 'Count');
    grid(hAx2, 'on');

    % Add histogram control buttons
    uicontrol('Parent', plotsTab, ...
              'Style', 'pushbutton', ...
              'String', 'Reset Histogram', ...
              'Position', [1200 100 150 30], ...
              'Callback', @resetHistogram);
          
    % Add checkbox for histogram mode
    hHistMode = uicontrol('Parent', plotsTab, ...
                         'Style', 'checkbox', ...
                         'String', 'Show Current Window Only (10ms)', ...
                         'Value', 0, ...
                         'Position', [1200 140 200 30], ...
                         'Callback', @toggleHistMode);

    %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
    % SECOND TAB: DETAILED STATISTICS
    %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
    statsTab = uitab('Parent', tabGroup, 'Title', 'Detailed Statistics');
    
    % Create statistics panel
    statPanel = uipanel('Parent', statsTab, ...
                       'Position', [0.05 0.05 0.9 0.9], ...
                       'Title', 'Channel Statistics (1s Window)', ...
                       'FontSize', 12, ...
                       'FontWeight', 'bold');
    
    % Create a table for statistics display with units
    columnNames = {'Channel', 'Mean (V)', 'Std Dev (V)', 'Min (V)', 'Max (V)', 'Power (mW)'};
    columnFormat = {'char', 'numeric', 'numeric', 'numeric', 'numeric', 'numeric'};
    columnEditable = [false false false false false false];
    
    hStatTable = uitable('Parent', statPanel, ...
                        'Data', cell(1,6), ...
                        'ColumnName', columnNames, ...
                        'ColumnFormat', columnFormat, ...
                        'ColumnEditable', columnEditable, ...
                        'Position', [20 20 800 100], ...
                        'FontSize', 11);

    % Set the duration for each read (1 ms)
    readDuration = seconds(0.001);
    windowDuration = 0.01; % 10ms window for display
    statsWindowDuration = 1.0; % 1s window for statistics
    maxBufferSize = statsWindowDuration * dq.Rate;
    displayBufferSize = windowDuration * dq.Rate;
    
    % Variables for data collection
    lastUpdateTime = 0;
    updateInterval = 0.001; % 1ms update interval for stats
    instantData = zeros(250,1); % Buffer for 1ms of data (250 samples at 250kHz)
    instantIndex = 1;
    cumulativeData = []; % Stores all acquired data for histogram
    showCurrentWindowOnly = false; % Flag for histogram mode

    % Create buffers for the data
    dataBuffer = [];
    timeBuffer = [];

    % Start the main loop
    while ishandle(hFig)
        % Read data for the specified duration
        data = read(dq, readDuration, "OutputFormat", "Matrix");
        timestamps = (0:size(data,1)-1)' / dq.Rate;
        
        % Store data for instant stats (1ms update)
        samplesToStore = min(size(data,1), 250-instantIndex+1);
        instantData(instantIndex:instantIndex+samplesToStore-1) = data(1:samplesToStore);
        instantIndex = instantIndex + samplesToStore;
        
        % Update buffers for visualization
        if isempty(timeBuffer)
            timeBuffer = timestamps;
        else
            timeBuffer = [timeBuffer; timestamps + timeBuffer(end) + 1/dq.Rate];
        end
        dataBuffer = [dataBuffer; data];
        cumulativeData = [cumulativeData; data]; % Store all data for histogram

        % Trim buffers to 1 second window (for statistics)
        if length(dataBuffer) > maxBufferSize
            samplesToRemove = length(dataBuffer) - maxBufferSize;
            dataBuffer = dataBuffer(samplesToRemove+1:end);
            timeBuffer = timeBuffer(samplesToRemove+1:end);
        end

        % Update time series plot
        set(hLine, 'XData', timeBuffer, 'YData', dataBuffer);

        % Update histogram based on current mode
        if showCurrentWindowOnly
            % Show only the current 10ms window
            if length(dataBuffer) > displayBufferSize
                histData = dataBuffer(end-displayBufferSize+1:end);
            else
                histData = dataBuffer;
            end
            title(hAx2, 'Ch5 Distribution (10ms Window)');
        else
            % Show all accumulated data
            histData = cumulativeData;
            title(hAx2, 'Ch5 Distribution (All Data)');
        end
        hHist.Data = histData;

        % Check if we've collected 1ms of data (250 samples at 250kHz)
        currentTime = toc;
        if instantIndex >= 250 || (currentTime - lastUpdateTime) >= updateInterval
            % Calculate instant statistics (1ms window)
            instantMean = mean(instantData(1:instantIndex-1));
            instantStddev = std(instantData(1:instantIndex-1));
            
            % Update real-time stats annotation on plot (1ms update)
            set(hStatsText, 'String', sprintf('Ch5: %.3f V\nσ: %.3f V', instantMean, instantStddev));
            
            % Reset instant buffer
            instantData = zeros(250,1);
            instantIndex = 1;
            lastUpdateTime = currentTime;
        end

        % Calculate statistics for 1s window (table update)
        meanVal = mean(dataBuffer);
        stddev = std(dataBuffer);
        minVal = min(dataBuffer);
        maxVal = max(dataBuffer);
        power = meanVal/10; % Adjust power calculation as needed
        
        % Update statistics table (1s window)
        statData = {'Ch5', meanVal, stddev, minVal, maxVal, power};
        set(hStatTable, 'Data', statData);

        % Set the x-axis limits for time series to show 10ms window
        if ~isempty(timeBuffer)
            currentXlim = [max(0, timeBuffer(end)-windowDuration), timeBuffer(end)];
            xlim(hAx1, currentXlim);
        end

        drawnow limitrate;
    end
    
    % Clean up when window is closed
    if isvalid(dq)
        release(dq);
    end

    % Callback functions
    function resetHistogram(~,~)
        cumulativeData = [];
        if showCurrentWindowOnly
            hHist.Data = [];
        else
            hHist.Data = cumulativeData;
        end
    end

    function toggleHistMode(source,~)
        showCurrentWindowOnly = source.Value;
        % Update histogram immediately when mode changes
        if showCurrentWindowOnly
            if length(dataBuffer) > displayBufferSize
                histData = dataBuffer(end-displayBufferSize+1:end);
            else
                histData = dataBuffer;
            end
            title(hAx2, 'Ch5 Distribution (10ms Window)');
        else
            histData = cumulativeData;
            title(hAx2, 'Ch5 Distribution (All Data)');
        end
        hHist.Data = histData;
    end
end
function NIPowerChecker()
    % Initialize the Data Acquisition
    d = daqlist("ni");
    if isempty(d)
        error('No NI DAQ devices found.');
    end
    deviceInfo = d{1, "DeviceInfo"};
    dq = daq("ni");
    dq.Rate = 250000;  % Set the sampling rate

    % Add input channels for ai0 to ai3
    for ch = 1:4
        addinput(dq, "Dev1", sprintf('ai%d', ch), "Voltage");
    end

    % Create main figure
    hFig = figure('Name', 'NI Power Checker - 10 FPS Update', ...
                 'NumberTitle', 'off', ...
                 'Position', [100, 100, 1400, 800]);
    
    % Create tab group
    tabGroup = uitabgroup('Parent', hFig);
    
    %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
    % FIRST TAB: PLOTS AND HISTOGRAMS
    %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
    plotsTab = uitab('Parent', tabGroup, 'Title', 'Plots & Stats');
    
    % Create a 2x2 grid of subplots
    hAx1 = subplot(2,4,[1 2], 'Parent', plotsTab);
    hold(hAx1, 'on');
    hAx2 = subplot(2,4,[3 4], 'Parent', plotsTab);
    hold(hAx2, 'on');
    
    hAx3 = subplot(2,4,5, 'Parent', plotsTab);
    hAx4 = subplot(2,4,6, 'Parent', plotsTab);
    hAx5 = subplot(2,4,7, 'Parent', plotsTab);
    hAx6 = subplot(2,4,8, 'Parent', plotsTab);

    ylabel(hAx1, 'Voltage (V)');
    ylabel(hAx2, 'Voltage (V)');
    xlabel(hAx1, 'Time (s)');
    xlabel(hAx2, 'Time (s)');
    grid(hAx1, 'on');
    grid(hAx2, 'on');

    hLines = gobjects(4, 1);
    colors = lines(4);
    lineWidth = 1.5;

    % Plot channels
    hLines(1) = plot(hAx1, NaN, NaN, 'DisplayName', 'Ch0', 'Color', colors(1, :), 'LineWidth', lineWidth);
    hLines(2) = plot(hAx1, NaN, NaN, 'DisplayName', 'Ch1', 'Color', colors(2, :), 'LineWidth', lineWidth);
    hLines(3) = plot(hAx2, NaN, NaN, 'DisplayName', 'Ch2', 'Color', colors(3, :), 'LineWidth', lineWidth);
    hLines(4) = plot(hAx2, NaN, NaN, 'DisplayName', 'Ch3', 'Color', colors(4, :), 'LineWidth', lineWidth);
                
    % Annotations
    hStatsText1 = annotation(plotsTab, 'textbox', [0.15 0.85 0.2 0.1], 'String', '', 'EdgeColor', 'none', 'FontSize', 10, 'FontWeight', 'bold', 'BackgroundColor', [1 1 1 0.7]);
    hStatsText2 = annotation(plotsTab, 'textbox', [0.15 0.75 0.2 0.1], 'String', '', 'EdgeColor', 'none', 'FontSize', 10, 'FontWeight', 'bold', 'BackgroundColor', [1 1 1 0.7]);
    hStatsText3 = annotation(plotsTab, 'textbox', [0.65 0.85 0.2 0.1], 'String', '', 'EdgeColor', 'none', 'FontSize', 10, 'FontWeight', 'bold', 'BackgroundColor', [1 1 1 0.7]);
    hStatsText4 = annotation(plotsTab, 'textbox', [0.65 0.75 0.2 0.1], 'String', '', 'EdgeColor', 'none', 'FontSize', 10, 'FontWeight', 'bold', 'BackgroundColor', [1 1 1 0.7]);

    % Histograms (Auto Binning)
    hHist = gobjects(4, 1);
    hHist(1) = histogram(hAx3, NaN, 'BinMethod', 'auto', 'FaceColor', colors(1, :));
    title(hAx3, 'Ch0 Distribution'); xlabel(hAx3, 'Voltage (V)'); grid(hAx3, 'on');
    
    hHist(2) = histogram(hAx4, NaN, 'BinMethod', 'auto', 'FaceColor', colors(2, :));
    title(hAx4, 'Ch1 Distribution'); xlabel(hAx4, 'Voltage (V)'); grid(hAx4, 'on');
    
    hHist(3) = histogram(hAx5, NaN, 'BinMethod', 'auto', 'FaceColor', colors(3, :));
    title(hAx5, 'Ch2 Distribution'); xlabel(hAx5, 'Voltage (V)'); grid(hAx5, 'on');
    
    hHist(4) = histogram(hAx6, NaN, 'BinMethod', 'auto', 'FaceColor', colors(4, :));
    title(hAx6, 'Ch3 Distribution'); xlabel(hAx6, 'Voltage (V)'); grid(hAx6, 'on');

    %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
    % SECOND TAB: DETAILED STATISTICS
    %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
    statsTab = uitab('Parent', tabGroup, 'Title', 'Detailed Statistics');
    statPanel = uipanel('Parent', statsTab, 'Position', [0.05 0.05 0.9 0.9], 'Title', 'Channel Statistics (1s Window)', 'FontSize', 12, 'FontWeight', 'bold');
    
    columnNames = {'Channel', 'Mean (V)', 'Std Dev (V)', 'Min (V)', 'Max (V)', 'Power (mW)'};
    columnFormat = {'char', 'numeric', 'numeric', 'numeric', 'numeric', 'numeric'};
    
    hStatTable = uitable('Parent', statPanel, ...
                        'Data', cell(4,6), ...
                        'ColumnName', columnNames, ...
                        'ColumnFormat', columnFormat, ...
                        'Position', [20 20 800 400], ...
                        'FontSize', 11);
    
    diffPanel = uipanel('Parent', statsTab, 'Position', [0.05 0.5 0.9 0.4], 'Title', 'Voltage Differences (V)', 'FontSize', 12, 'FontWeight', 'bold');
    hDiffText1 = uicontrol('Parent', diffPanel, 'Style', 'text', 'Units', 'normalized', 'Position', [0.1 0.7 0.8 0.2], 'String', 'Ch0 - Ch1: 0.000 V', 'FontSize', 12, 'FontWeight', 'bold', 'HorizontalAlignment', 'left');
    hDiffText2 = uicontrol('Parent', diffPanel, 'Style', 'text', 'Units', 'normalized', 'Position', [0.1 0.4 0.8 0.2], 'String', 'Ch2 - Ch3: 0.000 V', 'FontSize', 12, 'FontWeight', 'bold', 'HorizontalAlignment', 'left');

    % Loop variables
    readDuration = seconds(0.001);
    windowDuration = 1.0;
    maxBufferSize = windowDuration * dq.Rate;
    
    tic; 
    
    % --- UPDATE RATE VARIABLES ---
    lastPlotUpdate = 0;
    plotInterval = 0.1; % 10 FPS = 0.1 seconds
    % -----------------------------
    
    lastStatsUpdate = 0;
    statsInterval = 0.001; % Keep stats calculation fast if needed, or sync with plot
    
    instantData = zeros(250,4); 
    instantIndex = 1;
    dataBuffer = [];
    timeBuffer = [];

    % --- MAIN LOOP ---
    while ishandle(hFig)
        % 1. Acquire Data (Fast - every 1ms)
        data = read(dq, readDuration, "OutputFormat", "Matrix");
        timestamps = (0:size(data,1)-1)' / dq.Rate;
        
        % Store for instant stats
        samplesToStore = min(size(data,1), 250-instantIndex+1);
        instantData(instantIndex:instantIndex+samplesToStore-1,:) = data(1:samplesToStore,:);
        instantIndex = instantIndex + samplesToStore;
        
        % Update buffers
        if isempty(timeBuffer)
            timeBuffer = timestamps;
        else
            timeBuffer = [timeBuffer; timestamps + timeBuffer(end) + 1/dq.Rate];
        end
        dataBuffer = [dataBuffer; data];

        % Trim buffers
        if length(dataBuffer) > maxBufferSize
            samplesToRemove = length(dataBuffer) - maxBufferSize;
            dataBuffer = dataBuffer(samplesToRemove+1:end, :);
            timeBuffer = timeBuffer(samplesToRemove+1:end);
        end

        currentTime = toc;

        % 2. Update PLOTS (Throttled - 10 FPS)
        if (currentTime - lastPlotUpdate) >= plotInterval
            
            % Update Line Plots
            for i = 1:4
                set(hLines(i), 'XData', timeBuffer, 'YData', dataBuffer(:, i));
                hHist(i).Data = dataBuffer(:, i);
            end

            % Dynamic Axis Scaling
            if ~isempty(dataBuffer)
                currentXlim = [max(0, timeBuffer(end)-windowDuration), timeBuffer(end)];
                xlim(hAx1, currentXlim);
                xlim(hAx2, currentXlim);

                ylims1 = getDynamicLimits(dataBuffer(:, 1:2));
                ylim(hAx1, ylims1);

                ylims2 = getDynamicLimits(dataBuffer(:, 3:4));
                ylim(hAx2, ylims2);
            end
            
            % Update Statistics GUI elements (Synced with plot update for efficiency)
            means = mean(dataBuffer);
            stddevs = std(dataBuffer);
            mins = min(dataBuffer);
            maxs = max(dataBuffer);
            powers = means/10; 
            
            statData = {
                'Ch0', means(1), stddevs(1), mins(1), maxs(1), powers(1);
                'Ch1', means(2), stddevs(2), mins(2), maxs(2), powers(2);
                'Ch2', means(3), stddevs(3), mins(3), maxs(3), powers(3);
                'Ch3', means(4), stddevs(4), mins(4), maxs(4), powers(4)};
            set(hStatTable, 'Data', statData);

            diff1 = means(1) - means(2);
            diff2 = means(3) - means(4);
            set(hDiffText1, 'String', sprintf('Ch0 - Ch1: %.3f V', diff1));
            set(hDiffText2, 'String', sprintf('Ch2 - Ch3: %.3f V', diff2));
            
            % Force draw
            drawnow;
            lastPlotUpdate = currentTime;
        end

        % 3. Fast Stats Calculation (Optional: Keep this fast if you want the text boxes to flicker faster, 
        % or move this inside the plot block above to also limit it to 10 FPS)
        if instantIndex >= 250 || (currentTime - lastStatsUpdate) >= statsInterval
            instantMeans = mean(instantData(1:instantIndex-1,:));
            instantStddevs = std(instantData(1:instantIndex-1,:));
            
            set(hStatsText1, 'String', sprintf('Ch0: %.3f V\nσ: %.3f V', instantMeans(1), instantStddevs(1)));
            set(hStatsText2, 'String', sprintf('Ch1: %.3f V\nσ: %.3f V', instantMeans(2), instantStddevs(2)));
            set(hStatsText3, 'String', sprintf('Ch2: %.3f V\nσ: %.3f V', instantMeans(3), instantStddevs(3)));
            set(hStatsText4, 'String', sprintf('Ch3: %.3f V\nσ: %.3f V', instantMeans(4), instantStddevs(4)));
            
            instantData = zeros(250,4);
            instantIndex = 1;
            lastStatsUpdate = currentTime;
        end
    end

    if isvalid(dq)
        release(dq);
    end
end

% --- HELPER FUNCTION ---
function lims = getDynamicLimits(dataSubset)
    curMin = min(dataSubset, [], 'all');
    curMax = max(dataSubset, [], 'all');
    
    if curMin == curMax
        if curMin == 0
            lims = [-0.1, 0.1];
        else
            lims = [curMin * 0.9, curMax * 1.1];
        end
    else
        range = curMax - curMin;
        padding = range * 0.1; 
        lims = [curMin - padding, curMax + padding];
    end
end
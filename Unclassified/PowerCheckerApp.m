classdef PowerCheckerApp < handle
    properties
        % Main UI handles
        fig
        tabGroup
        plotsTab
        statsTab
        motorTab
        
        % DAQ properties
        dq
        rate = 250000
        channel = 'ai5'
        
        % Plot handles
        timeAxes
        histAxes
        timePlot
        histPlot
        statsText
        
        % Data buffers
        timeBuffer
        dataBuffer
        cumulativeData
        instantData = zeros(250,1)
        
        % Motor control
        gpibObj
        motorConnected = false
        currentPosition = 'N/A'
        
        % UI controls
        histModeCheck
        resetHistButton
        connectGPIBButton
        gpibAddressEdit
        gpibStatusText
        targetPosEdit
        moveButton
        currentPosText
        velocityEdit
        accelEdit
        decelEdit
        motorStatusText
        statTable
    end
    
    methods
        function obj = PowerCheckerApp()
            % Initialize the application
            obj.initializeDAQ();
            obj.createUI();
            obj.setupCallbacks();
            
            % Start data acquisition
            obj.startAcquisition();
        end
        
        function initializeDAQ(obj)
            % Configure NI DAQ
            try
                d = daqlist("ni");
                deviceInfo = d{1, "DeviceInfo"};
                obj.dq = daq("ni");
                obj.dq.Rate = obj.rate;
                addinput(obj.dq, "Dev1", obj.channel, "Voltage");
            catch e
                errordlg(['DAQ initialization failed: ' e.message], 'DAQ Error');
                error('DAQ initialization failed');
            end
        end
        
        function createUI(obj)
            % Create main figure
            obj.fig = figure('Name', 'NI Power Checker with Motor Control', ...
                            'NumberTitle', 'off', ...
                            'Position', [100, 100, 1400, 800], ...
                            'CloseRequestFcn', @(~,~) obj.cleanup());
            
            % Create tab group
            obj.tabGroup = uitabgroup('Parent', obj.fig);
            
            % Create tabs
            obj.createPlotsTab();
            obj.createStatsTab();
            obj.createMotorTab();
        end
        
        function createPlotsTab(obj)
            % Plots and Histograms tab
            obj.plotsTab = uitab('Parent', obj.tabGroup, 'Title', 'Plots & Stats');
            
            % Time series plot
            obj.timeAxes = subplot(2,1,1, 'Parent', obj.plotsTab);
            hold(obj.timeAxes, 'on');
            ylim(obj.timeAxes, [0 1]);
            ylabel(obj.timeAxes, 'Voltage (V)');
            xlabel(obj.timeAxes, 'Time (s)');
            grid(obj.timeAxes, 'on');
            
            obj.timePlot = plot(obj.timeAxes, NaN, NaN, ...
                              'DisplayName', 'Ch5', ...
                              'Color', [0 0.4470 0.7410], ...
                              'LineWidth', 1.5);
            
            % Histogram plot
            obj.histAxes = subplot(2,1,2, 'Parent', obj.plotsTab);
            histEdges = linspace(0, 3, 50);
            obj.histPlot = histogram(obj.histAxes, NaN, ...
                                   'BinEdges', histEdges, ...
                                   'FaceColor', [0 0.4470 0.7410]);
            title(obj.histAxes, 'Ch5 Distribution (All Data)');
            xlabel(obj.histAxes, 'Voltage (V)');
            ylabel(obj.histAxes, 'Count');
            grid(obj.histAxes, 'on');
            
            % Real-time stats annotation
            obj.statsText = annotation(obj.plotsTab, 'textbox', ...
                                      [0.15 0.85 0.2 0.1], ...
                                      'String', '', ...
                                      'EdgeColor', 'none', ...
                                      'FontSize', 10, ...
                                      'FontWeight', 'bold', ...
                                      'BackgroundColor', [1 1 1 0.7]);
            
            % Histogram controls
            obj.resetHistButton = uicontrol('Parent', obj.plotsTab, ...
                                           'Style', 'pushbutton', ...
                                           'String', 'Reset Histogram', ...
                                           'Position', [1200 100 150 30]);
            
            obj.histModeCheck = uicontrol('Parent', obj.plotsTab, ...
                                         'Style', 'checkbox', ...
                                         'String', 'Show Current Window Only (10ms)', ...
                                         'Value', 0, ...
                                         'Position', [1200 140 200 30]);
        end
        
        function createStatsTab(obj)
            % Detailed statistics tab
            obj.statsTab = uitab('Parent', obj.tabGroup, 'Title', 'Detailed Stats');
            
            statPanel = uipanel('Parent', obj.statsTab, ...
                              'Position', [0.05 0.05 0.9 0.9], ...
                              'Title', 'Channel Statistics (1s Window)', ...
                              'FontSize', 12, ...
                              'FontWeight', 'bold');
            
            columnNames = {'Channel', 'Mean (V)', 'Std Dev (V)', 'Min (V)', 'Max (V)', 'Power (mW)'};
            columnFormat = {'char', 'numeric', 'numeric', 'numeric', 'numeric', 'numeric'};
            
            obj.statTable = uitable('Parent', statPanel, ...
                                  'Data', cell(1,6), ...
                                  'ColumnName', columnNames, ...
                                  'ColumnFormat', columnFormat, ...
                                  'ColumnEditable', false, ...
                                  'Position', [20 20 800 100], ...
                                  'FontSize', 11);
        end
        
        function createMotorTab(obj)
            % Motor control tab
            obj.motorTab = uitab('Parent', obj.tabGroup, 'Title', 'Motor Control');
            
            motorPanel = uipanel('Parent', obj.motorTab, ...
                               'Position', [0.05 0.05 0.9 0.9], ...
                               'Title', 'ESP Motor Controller (GPIB)', ...
                               'FontSize', 12, ...
                               'FontWeight', 'bold');
            
            % GPIB Connection Controls
            uicontrol('Parent', motorPanel, ...
                     'Style', 'text', ...
                     'String', 'GPIB Address:', ...
                     'Position', [50 400 100 20], ...
                     'FontSize', 10);
                 
            obj.gpibAddressEdit = uicontrol('Parent', motorPanel, ...
                                           'Style', 'edit', ...
                                           'String', '1', ...
                                           'Position', [160 400 50 25], ...
                                           'FontSize', 10);
                                       
            obj.connectGPIBButton = uicontrol('Parent', motorPanel, ...
                                            'Style', 'pushbutton', ...
                                            'String', 'Connect', ...
                                            'Position', [220 400 80 25], ...
                                            'FontSize', 10);
                                       
            obj.gpibStatusText = uicontrol('Parent', motorPanel, ...
                                          'Style', 'text', ...
                                          'String', 'Status: Disconnected', ...
                                          'Position', [310 400 150 20], ...
                                          'FontSize', 10, ...
                                          'ForegroundColor', 'red');
            
            % Position Controls
            uicontrol('Parent', motorPanel, ...
                     'Style', 'text', ...
                     'String', 'Target Position:', ...
                     'Position', [50 350 100 20], ...
                     'FontSize', 10);
                 
            obj.targetPosEdit = uicontrol('Parent', motorPanel, ...
                                         'Style', 'edit', ...
                                         'String', '0', ...
                                         'Position', [160 350 100 25], ...
                                         'FontSize', 10);
                                     
            obj.moveButton = uicontrol('Parent', motorPanel, ...
                                     'Style', 'pushbutton', ...
                                     'String', 'Move', ...
                                     'Position', [270 350 80 25], ...
                                     'FontSize', 10);
                                 
            uicontrol('Parent', motorPanel, ...
                     'Style', 'text', ...
                     'String', 'Current Position:', ...
                     'Position', [50 300 100 20], ...
                     'FontSize', 10);
                 
            obj.currentPosText = uicontrol('Parent', motorPanel, ...
                                         'Style', 'text', ...
                                         'String', 'N/A', ...
                                         'Position', [160 300 100 20], ...
                                         'FontSize', 10);
            
            % Motion Parameters
            uicontrol('Parent', motorPanel, ...
                     'Style', 'text', ...
                     'String', 'Velocity:', ...
                     'Position', [50 250 100 20], ...
                     'FontSize', 10);
                 
            obj.velocityEdit = uicontrol('Parent', motorPanel, ...
                                       'Style', 'edit', ...
                                       'String', '10', ...
                                       'Position', [160 250 100 25], ...
                                       'FontSize', 10);
                                   
            uicontrol('Parent', motorPanel, ...
                     'Style', 'text', ...
                     'String', 'Acceleration:', ...
                     'Position', [50 200 100 20], ...
                     'FontSize', 10);
                 
            obj.accelEdit = uicontrol('Parent', motorPanel, ...
                                    'Style', 'edit', ...
                                    'String', '2', ...
                                    'Position', [160 200 100 25], ...
                                    'FontSize', 10);
                               
            uicontrol('Parent', motorPanel, ...
                     'Style', 'text', ...
                     'String', 'Deceleration:', ...
                     'Position', [50 150 100 20], ...
                     'FontSize', 10);
                 
            obj.decelEdit = uicontrol('Parent', motorPanel, ...
                                    'Style', 'edit', ...
                                    'String', '2', ...
                                    'Position', [160 150 100 25], ...
                                    'FontSize', 10);
                               
            % Status
            obj.motorStatusText = uicontrol('Parent', motorPanel, ...
                                           'Style', 'text', ...
                                           'String', 'Status: Ready', ...
                                           'Position', [50 100 200 20], ...
                                           'FontSize', 10);
        end
        
        function setupCallbacks(obj)
            % Set up all UI callbacks
            set(obj.resetHistButton, 'Callback', @(~,~) obj.resetHistogram());
            set(obj.histModeCheck, 'Callback', @(~,~) obj.toggleHistMode());
            set(obj.connectGPIBButton, 'Callback', @(~,~) obj.connectGPIB());
            set(obj.moveButton, 'Callback', @(~,~) obj.moveMotor());
            set(obj.velocityEdit, 'Callback', @(~,~) obj.updateMotionParams());
            set(obj.accelEdit, 'Callback', @(~,~) obj.updateMotionParams());
            set(obj.decelEdit, 'Callback', @(~,~) obj.updateMotionParams());
        end
        
        function startAcquisition(obj)
            % Start the data acquisition loop
            readDuration = seconds(0.001);
            windowDuration = 0.01;
            statsWindowDuration = 1.0;
            maxBufferSize = statsWindowDuration * obj.rate;
            displayBufferSize = windowDuration * obj.rate;
            
            lastUpdateTime = 0;
            updateInterval = 0.001;
            instantIndex = 1;
            
            while ishandle(obj.fig)
                % Read data
                data = read(obj.dq, readDuration, "OutputFormat", "Matrix");
                timestamps = (0:size(data,1)-1)' / obj.rate;
                
                % Store instant data
                samplesToStore = min(size(data,1), 250-instantIndex+1);
                obj.instantData(instantIndex:instantIndex+samplesToStore-1) = data(1:samplesToStore);
                instantIndex = instantIndex + samplesToStore;
                
                % Update buffers
                if isempty(obj.timeBuffer)
                    obj.timeBuffer = timestamps;
                else
                    obj.timeBuffer = [obj.timeBuffer; timestamps + obj.timeBuffer(end) + 1/obj.rate];
                end
                obj.dataBuffer = [obj.dataBuffer; data];
                obj.cumulativeData = [obj.cumulativeData; data];
                
                % Trim buffers
                if length(obj.dataBuffer) > maxBufferSize
                    samplesToRemove = length(obj.dataBuffer) - maxBufferSize;
                    obj.dataBuffer = obj.dataBuffer(samplesToRemove+1:end);
                    obj.timeBuffer = obj.timeBuffer(samplesToRemove+1:end);
                end
                
                % Update plots
                obj.updatePlots(displayBufferSize);
                
                % Update stats
                currentTime = toc;
                if instantIndex >= 250 || (currentTime - lastUpdateTime) >= updateInterval
                    obj.updateInstantStats();
                    instantIndex = 1;
                    lastUpdateTime = currentTime;
                end
                
                % Update motor status
                obj.updateMotorStatus();
                
                drawnow limitrate;
            end
        end
        
        function updatePlots(obj, displayBufferSize)
            % Update time series plot
            set(obj.timePlot, 'XData', obj.timeBuffer, 'YData', obj.dataBuffer);
            
            % Update histogram based on mode
            if get(obj.histModeCheck, 'Value')
                % Current window only
                if length(obj.dataBuffer) > displayBufferSize
                    histData = obj.dataBuffer(end-displayBufferSize+1:end);
                else
                    histData = obj.dataBuffer;
                end
                title(obj.histAxes, 'Ch5 Distribution (10ms Window)');
            else
                % All data
                histData = obj.cumulativeData;
                title(obj.histAxes, 'Ch5 Distribution (All Data)');
            end
            obj.histPlot.Data = histData;
            
            % Update x-axis limits
            if ~isempty(obj.timeBuffer)
                currentXlim = [max(0, obj.timeBuffer(end)-0.01), obj.timeBuffer(end)];
                xlim(obj.timeAxes, currentXlim);
            end
        end
        
        function updateInstantStats(obj)
            % Calculate and display instant statistics
            instantMean = mean(obj.instantData(1:end-1));
            instantStddev = std(obj.instantData(1:end-1));
            
            set(obj.statsText, 'String', sprintf('Ch5: %.3f V\nσ: %.3f V', instantMean, instantStddev));
            
            % Reset instant buffer
            obj.instantData = zeros(250,1);
            
            % Update statistics table
            meanVal = mean(obj.dataBuffer);
            stddev = std(obj.dataBuffer);
            minVal = min(obj.dataBuffer);
            maxVal = max(obj.dataBuffer);
            power = meanVal/10;
            
            statData = {'Ch5', meanVal, stddev, minVal, maxVal, power};
            set(obj.statTable, 'Data', statData);
        end
        
        function resetHistogram(obj)
            % Reset the cumulative data buffer
            obj.cumulativeData = [];
            if get(obj.histModeCheck, 'Value')
                obj.histPlot.Data = [];
            else
                obj.histPlot.Data = obj.cumulativeData;
            end
        end
        
        function toggleHistMode(obj)
            % Toggle between current window and all data modes
            if get(obj.histModeCheck, 'Value')
                title(obj.histAxes, 'Ch5 Distribution (10ms Window)');
            else
                title(obj.histAxes, 'Ch5 Distribution (All Data)');
            end
        end
        
        function connectGPIB(obj)
            % Establish GPIB connection
            try
                % Close existing connection
                if ~isempty(obj.gpibObj) && isvalid(obj.gpibObj)
                    fclose(obj.gpibObj);
                    delete(obj.gpibObj);
                end
                
                % Get GPIB address
                gpibAddr = str2double(get(obj.gpibAddressEdit, 'String'));
                if isnan(gpibAddr) || gpibAddr < 0 || gpibAddr > 30
                    error('Invalid GPIB address (0-30)');
                end
                
                % Create GPIB object
                if ispc
                    obj.gpibObj = visa('ni', ['GPIB0::' num2str(gpibAddr) '::INSTR']);
                else
                    obj.gpibObj = visa('agilent', ['GPIB0::' num2str(gpibAddr) '::INSTR']);
                end
                
                % Configure connection
                obj.gpibObj.InputBufferSize = 1024;
                obj.gpibObj.Timeout = 2;
                fopen(obj.gpibObj);
                
                % Test communication
                fprintf(obj.gpibObj, '*IDN?');
                idn = fscanf(obj.gpibObj);
                if isempty(idn)
                    error('No response from instrument');
                end
                
                obj.motorConnected = true;
                set(obj.gpibStatusText, 'String', ['Status: Connected to ' strtrim(idn)], ...
                                      'ForegroundColor', 'green');
                
                % Initialize motor
                obj.sendGPIBCommand('1MO');
                pause(0.5);
                obj.sendGPIBCommand('1AC2');
                obj.sendGPIBCommand('1AG2');
                obj.sendGPIBCommand('1VA10');
                
            catch e
                obj.motorConnected = false;
                set(obj.gpibStatusText, 'String', ['Status: ' e.message], 'ForegroundColor', 'red');
                if ~isempty(obj.gpibObj) && isvalid(obj.gpibObj)
                    fclose(obj.gpibObj);
                    delete(obj.gpibObj);
                    obj.gpibObj = [];
                end
            end
        end
        
        function response = sendGPIBCommand(obj, cmd)
            % Send command to GPIB device
            response = '';
            if ~obj.motorConnected || isempty(obj.gpibObj), return; end
            
            try
                fprintf(obj.gpibObj, cmd);
                if contains(cmd, '?')
                    response = fscanf(obj.gpibObj);
                end
            catch e
                obj.motorConnected = false;
                set(obj.gpibStatusText, 'String', ['Status: ' e.message], 'ForegroundColor', 'red');
            end
        end
        
        function moveMotor(obj)
            % Move motor to target position
            if ~obj.motorConnected, return; end
            
            try
                target = str2double(get(obj.targetPosEdit, 'String'));
                if isnan(target)
                    errordlg('Invalid target position', 'Input Error');
                    return;
                end
                
                set(obj.motorStatusText, 'String', 'Status: Moving...', 'ForegroundColor', 'red');
                obj.sendGPIBCommand(['1PA' num2str(target)]);
                
            catch e
                errordlg(['Motor movement error: ' e.message], 'Motor Error');
                set(obj.motorStatusText, 'String', 'Status: Error', 'ForegroundColor', 'red');
            end
        end
        
        function updateMotionParams(obj)
            % Update motor motion parameters
            if ~obj.motorConnected, return; end
            
            try
                vel = str2double(get(obj.velocityEdit, 'String'));
                accel = str2double(get(obj.accelEdit, 'String'));
                decel = str2double(get(obj.decelEdit, 'String'));
                
                if any(isnan([vel, accel, decel]))
                    errordlg('Invalid motion parameters', 'Input Error');
                    return;
                end
                
                obj.sendGPIBCommand(['1VA' num2str(vel)]);
                obj.sendGPIBCommand(['1AC' num2str(accel)]);
                obj.sendGPIBCommand(['1AG' num2str(decel)]);
                
            catch e
                errordlg(['Parameter update error: ' e.message], 'Motor Error');
            end
        end
        
        function updateMotorStatus(obj)
            % Update motor position and status
            if ~obj.motorConnected, return; end
            
            try
                position = obj.sendGPIBCommand('1TP');
                set(obj.currentPosText, 'String', position);
                
                motionStatus = obj.sendGPIBCommand('1MD');
                if contains(motionStatus, '0')
                    set(obj.motorStatusText, 'String', 'Status: Ready', 'ForegroundColor', 'green');
                else
                    set(obj.motorStatusText, 'String', 'Status: Moving...', 'ForegroundColor', 'red');
                end
            catch
                set(obj.motorStatusText, 'String', 'Status: Comm Error', 'ForegroundColor', 'red');
            end
        end
        
        function cleanup(obj)
            % Clean up resources when closing
            if isvalid(obj.dq)
                release(obj.dq);
            end
            
            if ~isempty(obj.gpibObj) && isvalid(obj.gpibObj)
                try
                    obj.sendGPIBCommand('1MF'); % Disable motor
                    fclose(obj.gpibObj);
                    delete(obj.gpibObj);
                catch
                end
            end
            
            delete(obj.fig);
        end
    end
end
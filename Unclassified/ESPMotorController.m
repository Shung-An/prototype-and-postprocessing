classdef ESPMotorController < handle
    properties
        % GPIB Connection
        gpibObj
        gpibAddress = 1
        isConnected = false
        
        % Motor Parameters
        currentPosition = 0
        targetPosition = 0
        velocity = 10      % mm/s
        acceleration = 2   % mm/s²
        deceleration = 2   % mm/s²
        
        % UI Handles
        fig
        statusPanel
        controlPanel
        configPanel
        
        % Status Monitoring
        isMoving = false
        lastUpdate = 0
        updateInterval = 0.2 % seconds
    end
    
    methods
        function obj = ESPMotorController()
            % Initialize the controller and UI
            obj.createUI();
            obj.setupCallbacks();
        end
        
        function createUI(obj)
            % Create main figure
            obj.fig = figure('Name', 'ESP Motor Controller', ...
                            'NumberTitle', 'off', ...
                            'Position', [100, 100, 600, 400], ...
                            'CloseRequestFcn', @(~,~) obj.cleanup());
            
            % Status Panel
            obj.statusPanel = uipanel('Parent', obj.fig, ...
                                    'Title', 'Status', ...
                                    'Position', [0.02, 0.7, 0.96, 0.28]);
            
            % Connection Controls
            uicontrol('Parent', obj.statusPanel, ...
                     'Style', 'text', ...
                     'String', 'GPIB Address:', ...
                     'Position', [10, 60, 80, 20]);
                 
            addrEdit = uicontrol('Parent', obj.statusPanel, ...
                                'Style', 'edit', ...
                                'String', num2str(obj.gpibAddress), ...
                                'Position', [100, 60, 50, 25], ...
                                'Tag', 'addrEdit');
                            
            uicontrol('Parent', obj.statusPanel, ...
                     'Style', 'pushbutton', ...
                     'String', 'Connect', ...
                     'Position', [160, 60, 80, 25], ...
                     'Callback', @(~,~) obj.connectGPIB(), ...
                     'Tag', 'connectBtn');
            
            obj.statusText = uicontrol('Parent', obj.statusPanel, ...
                                     'Style', 'text', ...
                                     'String', 'Disconnected', ...
                                     'Position', [250, 60, 200, 20], ...
                                     'ForegroundColor', 'red', ...
                                     'FontWeight', 'bold');
            
            % Position Display
            uicontrol('Parent', obj.statusPanel, ...
                     'Style', 'text', ...
                     'String', 'Position (mm):', ...
                     'Position', [10, 20, 100, 20]);
                 
            obj.posDisplay = uicontrol('Parent', obj.statusPanel, ...
                                     'Style', 'text', ...
                                     'String', '0.000', ...
                                     'Position', [120, 20, 100, 20], ...
                                     'FontWeight', 'bold');
            
            % Control Panel
            obj.controlPanel = uipanel('Parent', obj.fig, ...
                                     'Title', 'Motion Control', ...
                                     'Position', [0.02, 0.35, 0.96, 0.35]);
            
            % Target Position
            uicontrol('Parent', obj.controlPanel, ...
                     'Style', 'text', ...
                     'String', 'Target Position (mm):', ...
                     'Position', [10, 80, 150, 20]);
                 
            obj.targetEdit = uicontrol('Parent', obj.controlPanel, ...
                                     'Style', 'edit', ...
                                     'String', '0', ...
                                     'Position', [170, 80, 100, 25]);
            
            % Move Buttons
            uicontrol('Parent', obj.controlPanel, ...
                     'Style', 'pushbutton', ...
                     'String', 'Move Absolute', ...
                     'Position', [280, 80, 120, 25], ...
                     'Callback', @(~,~) obj.moveAbsolute());
            
            % Jog Controls
            uicontrol('Parent', obj.controlPanel, ...
                     'Style', 'pushbutton', ...
                     'String', 'Jog +1mm', ...
                     'Position', [10, 40, 100, 25], ...
                     'Callback', @(~,~) obj.jog(1));
            
            uicontrol('Parent', obj.controlPanel, ...
                     'Style', 'pushbutton', ...
                     'String', 'Jog -1mm', ...
                     'Position', [120, 40, 100, 25], ...
                     'Callback', @(~,~) obj.jog(-1));
            
            % Stop Button
            uicontrol('Parent', obj.controlPanel, ...
                     'Style', 'pushbutton', ...
                     'String', 'STOP', ...
                     'Position', [280, 40, 120, 25], ...
                     'BackgroundColor', [1, 0.6, 0.6], ...
                     'Callback', @(~,~) obj.stopMotor());
            
            % Configuration Panel
            obj.configPanel = uipanel('Parent', obj.fig, ...
                                    'Title', 'Configuration', ...
                                    'Position', [0.02, 0.02, 0.96, 0.33]);
            
            % Motion Parameters
            uicontrol('Parent', obj.configPanel, ...
                     'Style', 'text', ...
                     'String', 'Velocity (mm/s):', ...
                     'Position', [10, 80, 120, 20]);
                 
            obj.velEdit = uicontrol('Parent', obj.configPanel, ...
                                  'Style', 'edit', ...
                                  'String', num2str(obj.velocity), ...
                                  'Position', [140, 80, 80, 25]);
            
            uicontrol('Parent', obj.configPanel, ...
                     'Style', 'text', ...
                     'String', 'Acceleration (mm/s²):', ...
                     'Position', [10, 50, 120, 20]);
                 
            obj.accelEdit = uicontrol('Parent', obj.configPanel, ...
                                     'Style', 'edit', ...
                                     'String', num2str(obj.acceleration), ...
                                     'Position', [140, 50, 80, 25]);
            
            uicontrol('Parent', obj.configPanel, ...
                     'Style', 'text', ...
                     'String', 'Deceleration (mm/s²):', ...
                     'Position', [10, 20, 120, 20]);
                 
            obj.decelEdit = uicontrol('Parent', obj.configPanel, ...
                                     'Style', 'edit', ...
                                     'String', num2str(obj.deceleration), ...
                                     'Position', [140, 20, 80, 25]);
            
            % Update Button
            uicontrol('Parent', obj.configPanel, ...
                     'Style', 'pushbutton', ...
                     'String', 'Update Parameters', ...
                     'Position', [240, 50, 150, 25], ...
                     'Callback', @(~,~) obj.updateMotionParams());
        end
        
        function setupCallbacks(obj)
            % Set up timer for status updates
            t = timer('ExecutionMode', 'fixedRate', ...
                     'Period', obj.updateInterval, ...
                     'TimerFcn', @(~,~) obj.updateStatus());
            start(t);
            set(obj.fig, 'UserData', t); % Store timer in figure
        end
        
        function connectGPIB(obj)
            % Handle GPIB connection/disconnection
            if obj.isConnected
                obj.disconnectGPIB();
                return;
            end
            
            try
                % Get GPIB address from UI
                obj.gpibAddress = str2double(get(findobj(obj.statusPanel, 'Tag', 'addrEdit'), 'String'));
                
                % Validate address
                if isnan(obj.gpibAddress) || obj.gpibAddress < 0 || obj.gpibAddress > 30
                    error('Invalid GPIB address (0-30)');
                end
                
                % Create GPIB connection
                if ispc
                    obj.gpibObj = visa('ni', ['GPIB0::' num2str(obj.gpibAddress) '::INSTR']);
                else
                    obj.gpibObj = visa('agilent', ['GPIB0::' num2str(obj.gpibAddress) '::INSTR']);
                end
                
                % Configure connection
                obj.gpibObj.InputBufferSize = 1024;
                obj.gpibObj.Timeout = 2;
                fopen(obj.gpibObj);
                
                % Verify communication
                idn = obj.sendCommand('*IDN?');
                if isempty(idn)
                    error('No response from controller');
                end
                
                % Initialize motor
                obj.sendCommand('1MO'); % Motor on
                pause(0.5);
                obj.updateMotionParams(); % Set default parameters
                
                % Update UI
                obj.isConnected = true;
                set(findobj(obj.statusPanel, 'Tag', 'connectBtn'), 'String', 'Disconnect');
                set(obj.statusText, 'String', ['Connected to ' strtrim(idn)], 'ForegroundColor', [0, 0.5, 0]);
                
            catch e
                % Clean up on error
                if ~isempty(obj.gpibObj) && isvalid(obj.gpibObj)
                    fclose(obj.gpibObj);
                    delete(obj.gpibObj);
                    obj.gpibObj = [];
                end
                
                % Show error
                set(obj.statusText, 'String', ['Error: ' e.message], 'ForegroundColor', 'red');
                errordlg(['Connection failed: ' e.message], 'GPIB Error');
            end
        end
        
        function disconnectGPIB(obj)
            % Cleanly disconnect GPIB
            try
                if ~isempty(obj.gpibObj) && isvalid(obj.gpibObj)
                    obj.sendCommand('1MF'); % Motor off
                    fclose(obj.gpibObj);
                    delete(obj.gpibObj);
                    obj.gpibObj = [];
                end
                
                obj.isConnected = false;
                set(findobj(obj.statusPanel, 'Tag', 'connectBtn'), 'String', 'Connect');
                set(obj.statusText, 'String', 'Disconnected', 'ForegroundColor', 'red');
                
            catch e
                set(obj.statusText, 'String', ['Error: ' e.message], 'ForegroundColor', 'red');
            end
        end
        
        function response = sendCommand(obj, cmd)
            % Send command to motor controller
            response = '';
            if ~obj.isConnected || isempty(obj.gpibObj)
                return;
            end
            
            try
                fprintf(obj.gpibObj, cmd);
                if contains(cmd, '?')
                    response = fscanf(obj.gpibObj);
                end
            catch e
                obj.isConnected = false;
                set(obj.statusText, 'String', ['Error: ' e.message], 'ForegroundColor', 'red');
            end
        end
        
        function updateStatus(obj)
            % Update position and status display
            if ~obj.isConnected || toc(obj.lastUpdate) < obj.updateInterval
                return;
            end
            
            try
                % Get current position
                posStr = obj.sendCommand('1TP?');
                if ~isempty(posStr)
                    obj.currentPosition = str2double(posStr);
                    set(obj.posDisplay, 'String', sprintf('%.3f', obj.currentPosition));
                end
                
                % Check motion status
                status = obj.sendCommand('1MD?');
                obj.isMoving = ~strcmpi(strtrim(status), '0');
                
                % Update UI indicators
                if obj.isMoving
                    set(obj.posDisplay, 'ForegroundColor', 'red');
                else
                    set(obj.posDisplay, 'ForegroundColor', 'black');
                end
                
                obj.lastUpdate = tic;
                
            catch e
                set(obj.statusText, 'String', ['Status Error: ' e.message], 'ForegroundColor', 'red');
            end
        end
        
        function moveAbsolute(obj)
            % Move to absolute position
            if ~obj.isConnected, return; end
            
            try
                target = str2double(get(obj.targetEdit, 'String'));
                if isnan(target)
                    error('Invalid target position');
                end
                
                obj.sendCommand(['1PA' num2str(target)]);
                
            catch e
                errordlg(['Move failed: ' e.message], 'Motion Error');
            end
        end
        
        function jog(obj, distance)
            % Jog motor by specified distance
            if ~obj.isConnected, return; end
            
            try
                obj.sendCommand(['1PR' num2str(distance)]);
            catch e
                errordlg(['Jog failed: ' e.message], 'Motion Error');
            end
        end
        
        function stopMotor(obj)
            % Emergency stop
            if ~obj.isConnected, return; end
            
            try
                obj.sendCommand('1ST');
            catch e
                errordlg(['Stop failed: ' e.message], 'Motion Error');
            end
        end
        
        function updateMotionParams(obj)
            % Update motion parameters from UI
            if ~obj.isConnected, return; end
            
            try
                % Get values from UI
                vel = str2double(get(obj.velEdit, 'String'));
                accel = str2double(get(obj.accelEdit, 'String'));
                decel = str2double(get(obj.decelEdit, 'String'));
                
                % Validate
                if any(isnan([vel, accel, decel])) || any([vel, accel, decel] <= 0)
                    error('Invalid parameters - must be positive numbers');
                end
                
                % Send to controller
                obj.sendCommand(['1VA' num2str(vel)]);
                obj.sendCommand(['1AC' num2str(accel)]);
                obj.sendCommand(['1AG' num2str(decel)]);
                
                % Update properties
                obj.velocity = vel;
                obj.acceleration = accel;
                obj.deceleration = decel;
                
                msgbox('Motion parameters updated successfully', 'Success');
                
            catch e
                errordlg(['Update failed: ' e.message], 'Parameter Error');
            end
        end
        
        function cleanup(obj)
            % Clean up resources
            try
                % Stop and delete timer
                t = get(obj.fig, 'UserData');
                if isa(t, 'timer')
                    stop(t);
                    delete(t);
                end
                
                % Disconnect GPIB
                if obj.isConnected
                    obj.disconnectGPIB();
                end
                
                % Delete figure
                delete(obj.fig);
                
            catch
                % Force cleanup if graceful fails
                delete(obj.fig);
            end
        end
    end
end
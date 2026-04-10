function fastHardwareCycleScan()
    % Parameters
    startPos = 0;       % Starting position (mm)
    endPos = -200;          % Ending position (mm)
    nCycles = 3;           % Number of cycles
    gpibAddress = 1;       % GPIB address
    pmtChannel = "ai5";    % PMT analog input channel
    scanRate = 5000;       % DAQ sampling rate (Hz)
    
    % Initialize Stage Connection
    stage = visa('ni', ['GPIB0::' num2str(gpibAddress) '::INSTR']);
    fopen(stage);
    
    % Configure Stage for Hardware Cycling
    fprintf(stage, 'xx');       % Enter command mode
    fprintf(stage, 'ep');       % End program
    fprintf(stage, 'cy');       % Begin cycle program
    fprintf(stage, '1mo');      % Motor on
    fprintf(stage, '1or1');     % Origin at start position
    fprintf(stage, '1ws1000');  % Wait 1000ms (1s) at turnarounds
    
    % Define the movement cycle (loop)
    fprintf(stage, 'dl loop');  % Define loop label
    fprintf(stage, sprintf('1pr%.3f', endPos));  % Move to +100mm
    fprintf(stage, '1ws1000');  % Wait 1000ms
    fprintf(stage, sprintf('1pr%.3f', startPos)); % Move to -100mm
    fprintf(stage, '1ws1000');  % Wait 1000ms
    fprintf(stage, sprintf('jl loop,%d', nCycles)); % Jump to loop, repeat nCycles
    
    % Initialize DAQ for PMT
    dq = daq("ni");
    dq.Rate = scanRate;
    ch = addinput(dq, "Dev1", pmtChannel, "Voltage");
    
    % Start Continuous Acquisition
    start(dq, "continuous");
    fprintf('Starting hardware-controlled cycle scan...\n');
    
    % Data Collection Variables
    dataBuffer = [];
    positionBuffer = [];
    timeBuffer = [];
    startTime = tic;
    
    % Main Acquisition Loop
    while true
        % Check cycle status (qp command)
        fprintf(stage, 'qp');
        status = fscanf(stage, '%s');
        
        if contains(status, 'IDLE')
            break; % Cycle complete
        end
        
        % Get current position
        fprintf(stage, '1tp?');
        currentPos = str2double(fscanf(stage, '%f'));
        
        % Read PMT data
        [newData, ~] = read(dq, floor(scanRate/10), "OutputFormat", "Matrix"); % 100ms chunks
        
        % Timestamp the data
        newTimes = toc(startTime) - (length(newData)-1:-1:0)'/scanRate;
        
        % Store data
        dataBuffer = [dataBuffer; newData];
        positionBuffer = [positionBuffer; repmat(currentPos, size(newData))];
        timeBuffer = [timeBuffer; newTimes];
        
        % Throttle polling to ~10Hz
        pause(0.1); 
    end
    
    % Cleanup
    stop(dq);
    fprintf(stage, '1mf'); % Motor off
    fclose(stage);
    delete(stage);
    release(dq);
    
    % Process and Save Data
    [uniquePos, ~, idx] = unique(positionBuffer);
    meanIntensity = accumarray(idx, dataBuffer, [], @mean);
    
    save('hardware_cycle_scan.mat', 'uniquePos', 'meanIntensity', ...
         'timeBuffer', 'positionBuffer', 'dataBuffer');
    
    % Plot Results
    figure;
    plot(uniquePos, meanIntensity, 'LineWidth', 1.5);
    xlabel('Stage Position (mm)');
    ylabel('PMT Intensity (V)');
    title(sprintf('Hardware Cycle Scan: %.1fmm to %.1fmm (%d cycles)', ...
         startPos, endPos, nCycles));
    grid on;
end
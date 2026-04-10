function controlNewportGPIB1()
    % Configuration
    gpibAddress = 1;       % Using GPIB address 1
    startPos = 0;          % Default start position (mm)
    endPos = 200;          % Default end position (mm)
    nCycles = 3;           % Default number of cycles
    dwellTime = 100;       % Dwell time in ms
    
    % Motion Parameters
    maxVelocity = 25;      % mm/s
    acceleration = 75;     % mm/s²
    deceleration = 75;     % mm/s²
    
    try
        % Establish GPIB connection
        stage = visadev("GPIB0::" + num2str(gpibAddress) + "::INSTR");
        stage.Timeout = 5;  % 5 second timeout
        
        % Verify connection
        writeline(stage, "*IDN?");
        idn = readline(stage);
        fprintf('Connected to: %s\n', idn);
        
        % Initialize stage
        initializeStage(stage, maxVelocity, acceleration, deceleration);
        
        % Main menu
        while true
            fprintf('\nMain Menu:\n');
            fprintf('1. Move to position\n');
            fprintf('2. Run cycle routine\n');
            fprintf('3. Set parameters\n');
            fprintf('4. Quit\n');
            
            choice = input('Select option: ', 's');
            
            switch choice
                case '1'
                    % Single position move
                    targetPos = input('Enter target position (mm): ');
                    moveToPosition(stage, targetPos);
                    
                case '2'
                    % Cycle routine
                    runCycleRoutine(stage, startPos, endPos, nCycles, dwellTime);
                    
                case '3'
                    % Parameter configuration
                    [startPos, endPos, nCycles, dwellTime] = setParameters();
                    
                case '4'
                    break;
                    
                otherwise
                    fprintf('Invalid choice\n');
            end
        end
        
    catch ME
        fprintf('Error: %s\n', ME.message);
        if exist('stage', 'var')
            emergencyStop(stage);
        end
    end
    
    % Clean shutdown
    if exist('stage', 'var') && isvalid(stage)
        safeShutdown(stage);
        clear stage;
    end
    fprintf('Program terminated\n');
end

function initializeStage(stage, vel, acc, dec)
    % Motor on
    writeline(stage, '1MO');
    pause(0.5);
    
    % Set motion parameters
    writeline(stage, sprintf('1VA%.2f', vel));
    writeline(stage, sprintf('1AC%.2f', acc));
    writeline(stage, sprintf('1AG%.2f', dec));
    writeline(stage, '1AU1'); % Auto-optimization
    
    % Verify parameters
    fprintf('Velocity set to: %.1f mm/s\n', str2double(queryStage(stage, '1VA?')));
end

function moveToPosition(stage, targetPos)
    % Command move
    writeline(stage, sprintf('1PA%.3f', targetPos));
    fprintf('Moving to %.2f mm...\n', targetPos);
    
    % Monitor progress
    startTime = tic;
    while true
        pos = str2double(queryStage(stage, '1TP?'));
        moving = ~strcmp(queryStage(stage, '1MD?'), '0');
        
        fprintf('Position: %.2f mm | Moving: %d | Elapsed: %.1fs\r', ...
                pos, moving, toc(startTime));
            
        if ~moving
            break;
        end
        
        if toc(startTime) > 300 % 5 minute timeout
            error('Movement timeout');
        end
        
        pause(0.1);
    end
    fprintf('\nMove completed in %.1f seconds\n', toc(startTime));
end

function runCycleRoutine(stage, startPos, endPos, nCycles, dwellTime)
    % Setup cycle routine
    commands = [
        "EP"
        "CY"
        "1MO"
        sprintf("1OR%.3f", startPos)
        sprintf("1WS%d", dwellTime)
        "DL CYCLE_LOOP"
        sprintf("1PA%.3f", endPos)
        sprintf("1WS%d", dwellTime)
        sprintf("1PA%.3f", startPos)
        sprintf("1WS%d", dwellTime)
        sprintf("JL CYCLE_LOOP,%d", nCycles)
        "EN"
        "1SR"
    ];
    
    % Execute commands
    for cmd = commands'
        writeline(stage, cmd{1});
        pause(0.05);
    end
    
    % Monitor progress
    fprintf('\nRunning cycle routine...\n');
    startTime = tic;
    cycleCount = 0;
    
    while cycleCount < nCycles
        pos = queryStage(stage, '1TP?');
        currentCycle = str2double(queryStage(stage, '1CP?'));
        
        if currentCycle > cycleCount
            cycleCount = currentCycle;
            fprintf('Cycle %d/%d completed | Elapsed: %.1fs\n', ...
                    cycleCount, nCycles, toc(startTime));
        end
        
        fprintf('Position: %s mm | Cycle: %d/%d\r', pos, currentCycle, nCycles);
        pause(0.2);
    end
    
    fprintf('\nCycle routine completed in %.1f seconds\n', toc(startTime));
end

function [startPos, endPos, nCycles, dwellTime] = setParameters()
    startPos = input('Enter start position (mm): ');
    endPos = input('Enter end position (mm): ');
    nCycles = input('Enter number of cycles: ');
    dwellTime = input('Enter dwell time (ms): ');
    
    fprintf('Parameters updated:\n');
    fprintf('  Start: %.1f mm\n  End: %.1f mm\n', startPos, endPos);
    fprintf('  Cycles: %d\n  Dwell: %d ms\n', nCycles, dwellTime);
end

function response = queryStage(stage, command)
    writeline(stage, command);
    response = strtrim(readline(stage));
    
    if contains(response, '?')
        error('Controller error: %s', response);
    end
end

function emergencyStop(stage)
    fprintf('\nEMERGENCY STOP!\n');
    try
        writeline(stage, '1AB'); % Hard stop
        writeline(stage, '1MF'); % Motor off
        pause(1);
    catch
    end
end

function safeShutdown(stage)
    fprintf('\nPerforming safe shutdown...\n');
    try
        writeline(stage, '1MF'); % Motor off
    catch
    end
end
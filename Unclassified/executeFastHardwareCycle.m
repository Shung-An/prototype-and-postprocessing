function executeFastHardwareCycle()
    % Stage Parameters
    gpibAddress = 1;       % GPIB address
    startPos = -100;       % Start position (mm)
    endPos = 100;          % End position (mm)
    nCycles = 5;           % Number of cycles
    dwellTime = 200;       % Dwell time in ms (minimized)
    
    % Motion Parameters (Optimized for speed)
    maxVelocity = 20;      % mm/s (adjust to stage max)
    acceleration = 50;     % mm/s² (aggressive but safe)
    deceleration = 50;     % mm/s²
    
    % Establish GPIB Connection
    stage = visa('ni', ['GPIB0::' num2str(gpibAddress) '::INSTR']);
    fopen(stage);
    
    % Configure Motion Parameters First
    fprintf(stage, 'xx');  % Enter command mode
    fprintf(stage, sprintf('1va%.3f', maxVelocity));
    fprintf(stage, sprintf('1ac%.3f', acceleration));
    fprintf(stage, sprintf('1ag%.3f', deceleration));
    fprintf(stage, '1au1'); % Enable auto acceleration optimization
    
    % Send Cycle Routine Commands
    commandSequence = {
        'ep'                % End any existing program
        'cy'                % Begin cycle program
        '1mo'              % Motor on
        sprintf('1or%.3f', startPos)  % Set origin
        sprintf('1ws%d', dwellTime)   % Dwell time
        
        % Movement loop
        'dl fast_loop'
        sprintf('1pa%.3f', endPos)    % Absolute move to end
        sprintf('1ws%d', dwellTime)
        sprintf('1pa%.3f', startPos)
        sprintf('1ws%d', dwellTime)
        sprintf('jl fast_loop,%d', nCycles)
        
        'en'                % End program
        '1sr'              % Start routine
    };
    
    % Execute commands with proper timing
    for cmd = commandSequence'
        fprintf(stage, cmd{1}); 
        pause(0.01);       % 5ms pause between commands
    end
    
    % Fast status monitoring
    fprintf('\nRunning optimized cycle...\n');
    tic;
    while toc < (nCycles * estimateCycleTime(startPos, endPos, maxVelocity) * 1.5)
        fprintf(stage, 'qp');
        status = strtrim(fscanf(stage));
        if contains(status, 'IDLE')
            break;
        end
        pause(0.2);  % Faster polling
    end
    
    % Cleanup
    fprintf(stage, '1mf');  % Motor off
    fclose(stage);
    delete(stage);
    fprintf('Completed %d cycles in %.1f seconds\n', nCycles, toc);
end

function t = estimateCycleTime(startPos, endPos, velocity)
    % Estimates time for one complete cycle (s)
    travel = abs(endPos - startPos);
    t = 2 * (travel/velocity);  % Basic estimate
    t = t * 1.2;               % Empirical correction
end
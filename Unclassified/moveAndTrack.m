function cyclePositionLog = runAbsoluteCycleAndRecord(gpibObj, startPos, endPos, dwellTime, numCycles, pollInterval)
% Run absolute-position ESP300 cycle and record + print positions
%
% Inputs:
%   gpibObj     – opened GPIB object
%   startPos    – starting absolute position (mm)
%   endPos      – ending absolute position (mm)
%   dwellTime   – wait at each end (sec)
%   numCycles   – number of back-and-forth cycles
%   pollInterval– time between polls (sec)
%
% Output:
%   cyclePositionLog – recorded position vector

    if nargin < 6, pollInterval = 0.2; end

    cyclePositionLog = [];

    fprintf(gpibObj, "1MO");
    fprintf(gpibObj, "1PA0;1WS1000");
    pause(1);

    for i = 1:numCycles
        fprintf("Cycle %d/%d → Moving to endPos = %.3f mm\n", i, numCycles, endPos);
        fprintf(gpibObj, sprintf("1PA%.3f", endPos));
        cyclePositionLog = [cyclePositionLog; pollUntilDone(gpibObj, pollInterval)];

        pause(dwellTime);

        fprintf("Cycle %d/%d ← Returning to startPos = %.3f mm\n", i, numCycles, startPos);
        fprintf(gpibObj, sprintf("1PA%.3f", startPos));
        cyclePositionLog = [cyclePositionLog; pollUntilDone(gpibObj, pollInterval)];

        pause(dwellTime);
    end

    fprintf("Cycle finished. Total points: %d\n", numel(cyclePositionLog));
end

function posSeries = pollUntilDone(gpibObj, interval)
    posSeries = [];

    while true
        fprintf(gpibObj, "1MD?");
        done = str2double(fscanf(gpibObj));

        fprintf(gpibObj, "1TP?");
        pos = str2double(fscanf(gpibObj));

        posSeries(end+1, 1) = pos;
        fprintf("    Position = %.4f mm | Done = %d\n", pos, done);

        if done == 1
            break;
        end

        pause(interval);
    end
end
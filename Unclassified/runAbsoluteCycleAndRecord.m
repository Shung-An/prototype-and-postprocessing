function [cyclePositionLog, timeLog] = runAbsoluteCycleAndRecord(gpibObj, startPos, endPos, dwellTime, numCycles, pollInterval)
% Run absolute-position ESP300 cycle with live time-position plot
%
% Outputs:
%   cyclePositionLog – recorded position vector
%   timeLog – timestamp vector in seconds

    if nargin < 6, pollInterval = 0.2; end

    cyclePositionLog = [];
    timeLog = [];

    fprintf(gpibObj, "1MO");
    fprintf(gpibObj, sprintf("1PA%.3f;1WS1000", startPos));
    pause(1);

    t0 = datetime('now');

    for i = 1:numCycles
        fprintf("Cycle %d/%d → Moving to endPos = %.3f mm\n", i, numCycles, endPos);
        [p1, t1] = pollUntilDone(gpibObj, pollInterval, t0);
        cyclePositionLog = [cyclePositionLog; p1];
        timeLog = [timeLog; t1];
        pause(dwellTime);

        fprintf("Cycle %d/%d ← Returning to startPos = %.3f mm\n", i, numCycles, startPos);
        [p2, t2] = pollUntilDone(gpibObj, pollInterval, t0);
        cyclePositionLog = [cyclePositionLog; p2];
        timeLog = [timeLog; t2];
        pause(dwellTime);
    end

    fprintf("Cycle finished. Total points: %d\n", numel(cyclePositionLog));

    % Plot
    figure('Name', 'ESP300 Position vs Time');
    plot(timeLog, cyclePositionLog, 'b.-');
    xlabel('Time (s)');
    ylabel('Position (mm)');
    title('ESP300 Motion Cycle');
    grid on;
end

function [posSeries, timeSeries] = pollUntilDone(gpibObj, interval, t0)
    posSeries = [];
    timeSeries = [];

    while true
        fprintf(gpibObj, "1MD?");
        done = str2double(fscanf(gpibObj));

        fprintf(gpibObj, "1TP?");
        pos = str2double(fscanf(gpibObj));
        t = seconds(datetime('now') - t0);

        posSeries(end+1, 1) = pos;
        timeSeries(end+1, 1) = t;

        fprintf("    t = %.2f s | Pos = %.4f mm | Done = %d\n", t, pos, done);

        if done == 1
            break;
        end

        pause(interval);
    end
end

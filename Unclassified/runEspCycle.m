function [posLog, voltLog] = runEspCycle(g, dq, amplitude, repeats, settleTime, doPlot)
% Run a parameterized motion cycle using ESP300 and NI DAQ
%
% Inputs:
%   g          - GPIB object for ESP300
%   dq         - DAQ session
%   amplitude  - movement distance (mm) per direction
%   repeats    - number of forward-backward cycles
%   settleTime - pause time after each motion (seconds)
%   doPlot     - if true, will show live plot

    if nargin < 5, settleTime = 0.2; end
    if nargin < 6, doPlot = true; end

    posLog = [];
    voltLog = [];

    if doPlot
        figure('Name', 'Cycle Voltage vs Position');
        hScatter = scatter(NaN, NaN, 'filled');
        xlabel("Position (mm)");
        ylabel("Voltage (V)");
        title("ESP300 Cycle");
        grid on;
        hold on;
    end

    % Initial setup
    fprintf(g, "1MO");  % Motor on
    fprintf(g, "1OR1;1WS1000");  % Home
    pause(1);

    for i = 1:repeats
        fprintf("Cycle %d of %d...\n", i, repeats);

        % Move +amplitude
        cmd1 = sprintf("1PR%.3f;1WS1000", amplitude);
        fprintf(g, cmd1);
        pause(settleTime);

        [p1, v1] = recordPoint(g, dq, seconds(0.001));
        posLog(end+1) = p1;
        voltLog(end+1) = v1;

        % Move -amplitude
        cmd2 = sprintf("1PR%.3f;1WS1000", -amplitude);
        fprintf(g, cmd2);
        pause(settleTime);

        [p2, v2] = recordPoint(g, dq, seconds(0.001));
        posLog(end+1) = p2;
        voltLog(end+1) = v2;

        if doPlot
            set(hScatter, 'XData', posLog, 'YData', voltLog);
            drawnow;
        end
    end

    disp("Cycle complete.");

    % Save data
    T = table(posLog(:), voltLog(:), ...
              'VariableNames', {'Position_mm', 'Voltage_V'});
    filename = sprintf('CycleScan_%s.csv', datestr(now, 'yyyymmdd_HHMMSS'));
    writetable(T, filename);
    fprintf("Saved to %s\n", filename);
end

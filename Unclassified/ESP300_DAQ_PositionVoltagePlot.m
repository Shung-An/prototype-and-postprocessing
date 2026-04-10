function ESP300_DAQ_PositionVoltagePlot()
    %% === ESP300 GPIB Setup ===
    addr = 1;   % GPIB address
    board = 0;  % GPIB board index
    instrreset;
    g = gpib("ni", board, addr);
    fopen(g);
    fprintf(g, "1MO"); % Enable motor mode
    disp("ESP300 connected.");

    %% === NI DAQ Setup ===
    dq = daq("ni");
    dq.Rate = 250000;  % 250 kHz
    ch = addinput(dq, "Dev1", "ai5", "Voltage");
    ch.TerminalConfig = "Differential";
    duration = 0.001;  % 1ms per sample window
    samplesPerWindow = duration * dq.Rate;

    %% === Visualization Setup ===
    figure('Name', 'Voltage vs Position', 'NumberTitle', 'off');
    hScatter = scatter(NaN, NaN, 'filled');
    xlabel("Position (mm)");
    ylabel("Voltage (V)");
    title("Live Voltage vs. Position");
    grid on;
    hold on;

    allPositions = [];
    allVoltages = [];

    %% === Live Acquisition Loop ===
    disp("Press Ctrl+C in Command Window to stop.");

    while ishandle(hScatter)
        try
            % --- 1. Read position from ESP300 ---
            fprintf(g, "1PA?");
            posStr = fscanf(g);
            position = str2double(posStr);

            % --- 2. Read voltage from DAQ ---
            voltageSamples = read(dq, seconds(duration));
            voltage = mean(voltageSamples.Variables);  % Average of 1ms window

            % --- 3. Store and update plot ---
            allPositions(end+1) = position;
            allVoltages(end+1) = voltage;
            set(hScatter, 'XData', allPositions, 'YData', allVoltages);

            drawnow limitrate;
        catch ME
            warning("Acquisition error: %s", ME.message);
            pause(0.1);
        end
    end

    %% === Save Results on Close ===
    out = table(allPositions(:), allVoltages(:), ...
                'VariableNames', {'Position_mm', 'Voltage_V'});
    filename = ['VPos_Log_' datestr(now, 'yyyymmdd_HHMMSS') '.csv'];
    writetable(out, filename);
    disp("Saved voltage-position data to: " + filename);

    %% === Cleanup ===
    fclose(g);
    delete(g);
    release(dq);
    disp("Disconnected from ESP300 and NI DAQ.");
end

function ESP300_DAQ_Final()
    %% === Setup ===
    [g, dq, selectedChannel] = configureSystem();
    sampleWindow = seconds(0.001);  % 1 ms DAQ window

    %% === Data Storage ===
    posData = [];
    voltData = [];

    %% === Plot ===
    figure('Name', 'Voltage vs Position', 'NumberTitle', 'off');
    hScatter = scatter(NaN, NaN, 'filled');
    xlabel('Position (mm)');
    ylabel('Voltage (V)');
    title('Voltage vs Position');
    grid on;
    hold on;

    %% === Menu Loop ===
    while true
        fprintf("\n===== ESP300 DAQ MENU =====\n");
        disp("1. Move to Absolute Position");
        disp("2. Move by Relative Distance");
        disp("3. Home Stage");
        disp("4. Record Voltage vs. Position");
        disp("5. Run Automated Scan");
        disp("6. Export & Exit");
        disp("7. Run Programmed Motion + DAQ Cycle");
        choice = input("Select an option [1–7]: ");

        switch choice
            case 1
                target = input("Enter absolute position (mm): ");
                cmd = sprintf("1PA%.3f;1WS1000", target);
                fprintf(g, cmd);
                disp("Moving...");

            case 2
                delta = input("Enter relative distance (mm): ");
                cmd = sprintf("1PR%.3f;1WS1000", delta);
                fprintf(g, cmd);
                disp("Relative move...");

            case 3
                fprintf(g, "1OR1;1WS1000");
                disp("Homing complete.");

            case 4
                [p, v] = recordPoint(g, dq, sampleWindow);
                posData(end+1) = p;
                voltData(end+1) = v;
                set(hScatter, 'XData', posData, 'YData', voltData); drawnow;
                fprintf("Logged: %.3f mm, %.4f V\n", p, v);

            case 5
                startPos = input("Start position (mm): ");
                endPos = input("End position (mm): ");
                stepSize = input("Step size (mm): ");
                for p = startPos:stepSize:endPos
                    fprintf(g, sprintf("1PA%.3f;1WS1000", p)); pause(0.5);
                    [pp, vv] = recordPoint(g, dq, sampleWindow);
                    posData(end+1) = pp; voltData(end+1) = vv;
                    set(hScatter, 'XData', posData, 'YData', voltData); drawnow;
                end

            case 6
                T = table(posData(:), voltData(:), ...
                    'VariableNames', {'Position_mm', 'Voltage_V'});
                filename = ['VPos_' datestr(now,'yyyymmdd_HHMMSS') '.csv'];
                writetable(T, filename);
                fprintf("Saved to %s\n", filename);
                break;

            case 7
                runProgrammedCycle(g, dq, sampleWindow, hScatter, posData, voltData);

            otherwise
                disp("Invalid selection.");
        end
    end

    %% === Cleanup ===
    fclose(g); delete(g); release(dq);
    disp("Disconnected.");
end

%% === Helper: Configure DAQ and Motor ===
function [g, dq, selectedChannel] = configureSystem()
    % --- ESP300 ---
    addr = 1; board = 0;
    instrreset;
    g = gpib("ni", board, addr);
    fopen(g);
    fprintf(g, "1MO"); disp("ESP300 connected.");

    % Motor config
    vel = input("Enter motor velocity (mm/s) [default=2.0]: ");
    acc = input("Enter acceleration (mm/s²) [default=0.5]: ");
    limMin = input("Enter soft limit MIN (mm) [default=-50]: ");
    limMax = input("Enter soft limit MAX (mm) [default=50]: ");
    if isempty(vel), vel = 2; end
    if isempty(acc), acc = 0.5; end
    if isempty(limMin), limMin = -50; end
    if isempty(limMax), limMax = 50; end
    fprintf(g, sprintf("1VA%.2f;1AC%.2f;1SL%.2f;1SR%.2f", vel, acc, limMin, limMax));
    disp("Motor configured.");

    % --- DAQ ---
    dq = daq("ni");
    dq.Rate = 250000;
    chList = "ai0" + (0:7);
    disp("Available Channels: " + strjoin(chList));
    selectedChannel = input("Select DAQ channel (e.g., 'ai5'): ", 's');
    if isempty(selectedChannel), selectedChannel = "ai5"; end
    addinput(dq, "Dev1", selectedChannel, "Voltage");
    dq.Channels(1).TerminalConfig = "Differential";
    disp("DAQ configured.");
end

%% === Helper: Record Single Data Point ===
function [position, voltage] = recordPoint(g, dq, duration)
    fprintf(g, "1PA?");
    position = str2double(fscanf(g));
    v = read(dq, duration);
    voltage = mean(v.Variables);
end

%% === Helper: Programmed Motion + DAQ Cycle ===
function runProgrammedCycle(g, dq, sampleWindow, hScatter, posData, voltData)
    % Define a custom sequence
    sequence = {
        "home",      [];  % Home
        "moveAbs",   5;
        "wait",      1;
        "moveAbs",   10;
        "wait",      1;
        "moveRel",   -2;
        "wait",      0.5;
    };

    for i = 1:size(sequence, 1)
        action = sequence{i,1};
        val = sequence{i,2};

        switch action
            case "home"
                fprintf(g, "1OR1;1WS1000");
                disp("Homing...");

            case "moveAbs"
                fprintf(g, sprintf("1PA%.3f;1WS1000", val));
                disp("Move to " + val);

            case "moveRel"
                fprintf(g, sprintf("1PR%.3f;1WS1000", val));
                disp("Relative move: " + val);

            case "wait"
                pause(val);

            otherwise
                warning("Unknown action: %s", action);
        end

        pause(0.3); % Ensure motion complete
        [p, v] = recordPoint(g, dq, sampleWindow);
        posData(end+1) = p;
        voltData(end+1) = v;
        set(hScatter, 'XData', posData, 'YData', voltData);
        drawnow;
    end

    disp("Programmed cycle complete.");
end

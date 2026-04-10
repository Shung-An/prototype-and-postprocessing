% ESP300 Main Console Script
clear; clc;

% === CONFIGURATION ===
addr = 1; % GPIB address (default 1)
board = 0;

% === CONNECT TO CONTROLLER ===
instrreset;
g = gpib("ni", board, addr);
fopen(g);
fprintf(g, "1MO"); % Enable motor mode
disp("Connected to ESP300 on GPIB address " + addr);

% === MAIN MENU LOOP ===
while true
    fprintf("\n--- ESP300 MAIN MENU ---\n");
    disp("1. Move & Track with Live Plot");
    disp("2. Read Current Configuration");
    disp("3. Set Velocity / Accel / Limits");
    disp("4. Home Axis");
    disp("5. Save Configuration to EEPROM");
    disp("6. Disconnect & Exit");
    choice = input("Select option [1–6]: ");

    switch choice
        case 1
            target = input("Enter absolute position (mm): ");
            moveAndTrack(g, target, 0.1);

        case 2
            readConfiguration(g);

        case 3
            setConfiguration(g);

        case 4
            fprintf(g, "1OR1;1WS1000");
            disp("Homing complete.");

        case 5
            fprintf(g, "1SSAV");
            disp("Configuration saved to EEPROM.");

        
        case 6
            break;

        case 8
            startPos = input("Enter start position (mm): ");
            endPos = input("Enter end position (mm): ");
            dwellTime = input("Enter dwell time at each end (s): ");
            numCycles = input("Enter number of cycles: ");
            pollInterval = input("Enter polling interval (s) [default = 0.1]: ");
            if isempty(pollInterval), pollInterval = 0.1; end

            cyclePositionLog = runAbsoluteCycleAndRecord(g, startPos, endPos, dwellTime, numCycles, pollInterval);
            disp("Absolute cycle complete. Use 'cyclePositionLog' for further analysis.");
            
        otherwise
            disp("Invalid option.");
    end
end

% === DISCONNECT ===
fclose(g);
delete(g);
disp("Disconnected. Done.");

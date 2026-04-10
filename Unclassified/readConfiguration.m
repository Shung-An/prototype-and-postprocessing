function readConfiguration(gpibObj)
% Display current ESP300 configuration
    commands = {
        "Velocity",      "1VA?"
        "Acceleration",  "1AC?"
        "Deceleration",  "1DEC?"
        "Low Limit",     "1SL?"
        "High Limit",    "1SR?"
        "Target Pos",    "1TP?"
        "Current Pos",   "1PA?"
        "Motion Mode",   "1MM?"
    };

    fprintf("\n--- CURRENT CONFIGURATION ---\n");
    for i = 1:size(commands,1)
        fprintf(gpibObj, commands{i,2});
        val = strtrim(fscanf(gpibObj));
        fprintf("%-15s: %s\n", commands{i,1}, val);
    end
end

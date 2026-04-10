function setConfiguration(gpibObj)
% Allow setting motion parameters on ESP300

    fprintf("\n--- SET CONFIGURATION ---\n");

    val = input("Velocity (mm/s) [Enter to skip]: ", 's');
    if ~isempty(val)
        fprintf(gpibObj, sprintf("1VA%s", val));
    end

    val = input("Acceleration (mm/s^2) [Enter to skip]: ", 's');
    if ~isempty(val)
        fprintf(gpibObj, sprintf("1AC%s", val));
    end

    val = input("Deceleration (mm/s^2) [Enter to skip]: ", 's');
    if ~isempty(val)
        fprintf(gpibObj, sprintf("1DEC%s", val));
    end

    val = input("Software Low Limit (mm) [Enter to skip]: ", 's');
    if ~isempty(val)
        fprintf(gpibObj, sprintf("1SL%s", val));
    end

    val = input("Software High Limit (mm) [Enter to skip]: ", 's');
    if ~isempty(val)
        fprintf(gpibObj, sprintf("1SR%s", val));
    end

    disp("Settings updated. You may now choose to save them.");
end

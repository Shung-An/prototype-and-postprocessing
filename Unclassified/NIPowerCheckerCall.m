function averagePowers = NIPowerCheckerCall()
    % Initialize the Data Acquisition
    d = daqlist("ni");
    deviceInfo = d{1, "DeviceInfo"};
    dq = daq("ni");
    dq.Rate = 250000;  % Set the sampling rate

    % Add input channels for ai0 to ai3
    for ch = 1:4
        addinput(dq, "Dev1", sprintf('ai%d', ch), "Voltage");
    end

    % Set the duration for the read
    readDuration = seconds(0.001);

    % Read data once
    data = read(dq, readDuration, "OutputFormat", "Matrix");

    % Calculate average voltages
    averageVoltages = mean(data);

    % Calculate average powers (assuming voltage/10 = power in mW)
    averagePowers = averageVoltages / 10;

end


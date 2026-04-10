function acquireAndAnalyzePMT()
    % DAQ Configuration
    dq = daq("ni");
    Fs = 10000;  % Sampling rate (Hz)
    dq.Rate = Fs;
    
    % PMT Channel Setup (adjust if your PMT is on different channel)
    chPMT = addinput(dq, "Dev1", "ai5", "Voltage");
    chPMT.Range = [-10 10]; % Set appropriate voltage range
    
    % Acquisition Parameters
    duration = 10; % seconds
    totalSamples = duration * Fs;
    
    fprintf('Starting 120-second PMT acquisition at %d Hz...\n', Fs);
    
    % Acquire data (blocking read)
    data = read(dq, totalSamples, "OutputFormat","Matrix");
    time = (0:totalSamples-1)'/Fs;
    
    % Cleanup DAQ
    clear dq;
    
    fprintf('Acquisition complete. Analyzing data...\n');
    
    % Perform FFT analysis
    L = length(data);
    Y = fft(data);
    P2 = abs(Y/L);
    P1 = P2(1:floor(L/2)+1);
    P1(2:end-1) = 2*P1(2:end-1);
    f = Fs*(0:(L/2))/L;
    
    % Create figure
    figure('Position', [100 100 1200 600]);
    
    % Time domain plot
    subplot(1,2,1);
    plot(time, data, 'b');
    xlabel('Time (s)');
    ylabel('PMT Intensity (V)');
    title('Time Domain Signal');
    grid on;
    xlim([0 duration]);
    
    % Frequency domain plot
    subplot(1,2,2);
    semilogx(f, 20*log10(P1), 'r');
    xlabel('Frequency (Hz)');
    ylabel('Magnitude (dB)');
    title('Single-Sided Amplitude Spectrum');
    grid on;
    
    % Mark top 3 peaks
    [pks,locs] = findpeaks(P1, 'MinPeakHeight',0.1*max(P1), 'SortStr','descend', 'NPeaks',3);
    hold on;
    plot(f(locs), 20*log10(pks), 'ro', 'MarkerSize', 10);
    legend('Spectrum', 'Dominant Frequencies');
    
    % Display peak frequencies
    text(0.02, 0.98, sprintf('Top Frequencies:\n%.2f Hz (%.1f dB)\n%.2f Hz (%.1f dB)\n%.2f Hz (%.1f dB)',...
        f(locs(1)), 20*log10(pks(1)),...
        f(locs(2)), 20*log10(pks(2)),...
        f(locs(3)), 20*log10(pks(3))),...
        'Units','normalized', 'VerticalAlignment','top', 'BackgroundColor','w');
    
    % Save data
    save('pmt_analysis.mat', 'time', 'data', 'f', 'P1', 'Fs');
    fprintf('Analysis complete. Data saved to pmt_analysis.mat\n');
end
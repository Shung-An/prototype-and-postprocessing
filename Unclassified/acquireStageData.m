function acquireAndAnalyzePMT()
    % DAQ Configuration
    dq = daq("ni");
    dq.Rate = 10000;  % 10 kHz sampling rate
    
    % PMT Channel Setup
    chPMT = addinput(dq, "Dev1", "ai5", "Voltage");
    chPMT.Range = [-10 10];
    
    % Create Figure with UI Controls
    hFig = figure('Name','PMT Data Acquisition & FFT Analysis',...
                 'Position',[100 100 1200 800],...
                 'CloseRequestFcn',@closeFigure);
    
    % Time Domain Plot
    hTimeAx = subplot(3,1,1);
    title(hTimeAx,'Time Domain Signal');
    xlabel(hTimeAx,'Time (s)');
    ylabel(hTimeAx,'Voltage (V)');
    grid(hTimeAx,'on');
    hold(hTimeAx,'on');
    hTimePlot = plot(hTimeAx, NaN, NaN, 'b-');
    
    % Frequency Domain Plot (FFT)
    hFreqAx = subplot(3,1,2);
    title(hFreqAx,'Frequency Spectrum');
    xlabel(hFreqAx,'Frequency (Hz)');
    ylabel(hFreqAx,'Magnitude (dB)');
    grid(hFreqAx,'on');
    hold(hFreqAx,'on');
    
    % Integrated Intensity Plot
    hIntAx = subplot(3,1,3);
    title(hIntAx,'Integrated PMT Intensity (100 ms bins)');
    xlabel(hIntAx,'Time (s)');
    ylabel(hIntAx,'Intensity (V·s)');
    grid(hIntAx,'on');
    hold(hIntAx,'on');
    hIntPlot = plot(hIntAx, NaN, NaN, 'r-');
    
    % UI Controls
    uicontrol('Style','pushbutton','String','Start/Stop',...
              'Position',[20 20 100 30],...
              'Callback',@toggleAcquisition);
          
    uicontrol('Style','pushbutton','String','Run FFT',...
              'Position',[140 20 100 30],...
              'Callback',@runFFT,...
              'Enable','off');
          
    uicontrol('Style','pushbutton','String','Save Data',...
              'Position',[260 20 100 30],...
              'Callback',@saveData,...
              'Enable','off');
    
    statusText = uicontrol('Style','text','String','Ready to Start',...
                          'Position',[380 20 400 30],...
                          'HorizontalAlignment','left');
    
    % Data Storage
    rawData = [];
    timeVector = [];
    isRunning = false;
    isAcquired = false;
    
    % Nested Functions
    function toggleAcquisition(~,~)
        if ~isRunning
            % Start acquisition
            rawData = [];
            timeVector = [];
            startTime = tic;
            
            % Configure DAQ
            dq.ScansAvailableFcn = @processData;
            dq.ScansAvailableFcnCount = dq.Rate/10; % 100ms chunks
            
            start(dq, "continuous");
            isRunning = true;
            updateStatus('Acquisition running - move stage manually');
            set(findobj(hFig,'String','Start/Stop'), 'String', 'Stop');
            set(findobj(hFig,'String','Run FFT'), 'Enable','off');
            set(findobj(hFig,'String','Save Data'), 'Enable','off');
        else
            % Stop acquisition
            stop(dq);
            isRunning = false;
            isAcquired = true;
            updateStatus('Acquisition complete - ready for analysis');
            set(findobj(hFig,'String','Start/Stop'), 'String', 'Start');
            set(findobj(hFig,'String','Run FFT'), 'Enable','on');
            set(findobj(hFig,'String','Save Data'), 'Enable','on');
            
            % Update time domain plot with full dataset
            set(hTimePlot, 'XData', timeVector, 'YData', rawData);
            xlim(hTimeAx, [0 max(timeVector)]);
            
            % Calculate and plot integrated intensity
            integrationWindow = 0.1; % 100 ms
            samplesPerWindow = round(dq.Rate * integrationWindow);
            nWindows = floor(length(rawData)/samplesPerWindow);
            
            intTime = zeros(nWindows,1);
            intData = zeros(nWindows,1);
            
            for i = 1:nWindows
                idx = (1:samplesPerWindow) + (i-1)*samplesPerWindow;
                intTime(i) = mean(timeVector(idx));
                intData(i) = trapz(timeVector(idx), rawData(idx));
            end
            
            set(hIntPlot, 'XData', intTime, 'YData', intData);
            xlim(hIntAx, [0 max(timeVector)]);
        end
    end

    function processData(src,~)
        [newData, newTime] = read(src, src.ScansAvailableFcnCount, "OutputFormat","Matrix");
        
        if ~isempty(newData)
            % Store raw data
            rawData = [rawData; newData];
            timeVector = [timeVector; newTime + toc(startTime)];
            
            % Update time domain plot (last 2 seconds)
            showDuration = 2; % seconds
            showIdx = timeVector > (timeVector(end) - showDuration);
            set(hTimePlot, 'XData', timeVector(showIdx), 'YData', rawData(showIdx));
            xlim(hTimeAx, [timeVector(find(showIdx,1)) timeVector(end)]);
            
            drawnow limitrate;
        end
    end

    function runFFT(~,~)
        if isempty(rawData)
            updateStatus('No data available for FFT');
            return;
        end
        
        % Calculate FFT
        L = length(rawData);
        Fs = dq.Rate;
        Y = fft(rawData);
        P2 = abs(Y/L);
        P1 = P2(1:floor(L/2)+1);
        P1(2:end-1) = 2*P1(2:end-1);
        f = Fs*(0:(L/2))/L;
        
        % Plot frequency spectrum
        cla(hFreqAx);
        semilogx(hFreqAx, f, 20*log10(P1), 'b-');
        xlabel(hFreqAx,'Frequency (Hz)');
        ylabel(hFreqAx,'Magnitude (dB)');
        title(hFreqAx,'Single-Sided Amplitude Spectrum');
        grid(hFreqAx,'on');
        
        % Find and mark dominant frequencies
        [~, locs] = findpeaks(P1, 'SortStr','descend', 'NPeaks',3);
        hold(hFreqAx,'on');
        plot(hFreqAx, f(locs), 20*log10(P1(locs)), 'ro');
        legend(hFreqAx,'Spectrum','Dominant Frequencies');
        
        % Display frequency information
        freqInfo = sprintf('Dominant Frequencies:\n%.1f Hz (%.1f dB)\n%.1f Hz (%.1f dB)\n%.1f Hz (%.1f dB)',...
                          f(locs(1)), 20*log10(P1(locs(1))),...
                          f(locs(2)), 20*log10(P1(locs(2))),...
                          f(locs(3)), 20*log10(P1(locs(3))));
        text(hFreqAx, 0.02, 0.98, freqInfo,...
             'Units','normalized',...
             'VerticalAlignment','top',...
             'BackgroundColor','w');
        
        updateStatus('FFT analysis completed');
    end

    function saveData(~,~)
        if isempty(rawData)
            updateStatus('No data to save');
            return;
        end
        
        timestamp = datestr(now,'yyyymmdd_HHMMSS');
        
        % Save raw data
        rawFileName = ['pmt_raw_' timestamp '.mat'];
        save(rawFileName, 'rawData', 'timeVector');
        
        % Save FFT results
        if ~isempty(hFreqAx.Children)
            fftData = get(hFreqAx.Children(end), {'XData','YData'});
            fftFileName = ['pmt_fft_' timestamp '.mat'];
            save(fftFileName, 'fftData');
        end
        
        updateStatus(sprintf('Data saved to %s and %s', rawFileName, fftFileName));
    end

    function updateStatus(msg)
        set(statusText, 'String', msg);
        drawnow;
    end

    function closeFigure(~,~)
        if isRunning
            stop(dq);
        end
        if isvalid(dq)
            release(dq);
        end
        delete(hFig);
    end
end
clear; 
daqreset;                               % prevent -50103 reservations
script_dir = fileparts(mfilename('fullpath'));

%% ==========================================
%% 1. USER PARAMETERS
%% ==========================================
span_mm        = 1.0;                   % total oscillation span (mm)
center_mm      = 25;                    % zero point (absolute position)
half_mm        = span_mm/2;             % ± around center
num_samples    = 4000;                  % live points to display
sample_pause_s = 0.02;                  % UI pacing (~50 Hz)
c              = 299792458;             % m/s (speed of light)

%% ==========================================
%% 2. HARDWARE SETUP
%% ==========================================
% --- DAQ Setup ---
s  = daq.createSession('ni');
ai = addAnalogInputChannel(s,'Dev1','ai5','Voltage');
% ai.TerminalConfig = 'SingleEnded';    % Uncomment if needed
% ai.Range = [-10 10];
cleanupObj = onCleanup(@() tryRelease(s));

% --- ESP300 GPIB Setup ---
try
    esp = visadev("GPIB0::1::INSTR");
    configureTerminator(esp,"CR");
    esp.Timeout = 1.0;
    flush(esp);
    
    % Controller Settings
    writeline(esp,"1MO");       % servo ON
    writeline(esp,"1AC0.1");    % accel
    writeline(esp,"1AG0.1");    % decel
    writeline(esp,"1VA0.1");    % velocity
    writeline(esp,"1FE100");    % following error limit

    % --- Go to ABSOLUTE ZERO first ---
    fprintf('Moving to center position (%.2f mm)...\n', center_mm);
    writeline(esp, sprintf("1PA%.4f", center_mm));
    pause(5); % Wait for move

    % --- Define Motion Boundaries ---
    left_mm  = center_mm - half_mm;
    right_mm = center_mm + half_mm;

    % --- Execute Program ---
    writeline(esp,"EX Scan1"); % Assumes 'Scan1' is programmed on device
    fprintf('Scanning started...\n');
    
catch ME
    error('Hardware Init Failed: %s\nCheck connections or GPIB address.', ME.message);
end

%% ==========================================
%% 3. REAL-TIME PLOT SETUP
%% ==========================================
positions  = nan(1,num_samples);
voltages   = nan(1,num_samples);

f  = figure('Name','Realtime Autocorrelation','Color','w');
ax = axes('Parent',f);
hLine = plot(ax, nan, nan, 'r.-', 'LineWidth', 1.2); hold(ax,'on');
hPeak = plot(ax, nan, nan, 'ko', 'MarkerSize',8,'LineWidth',1.2);
grid(ax,'on');
xlabel(ax,'Position (mm)'); ylabel(ax,'DAQ Voltage (V)');
xlim([left_mm right_mm]);

% --- Top axis (Time Delay in ps) ---
% Fixed the 'positionsition' typo here
top_ax = axes('Position', get(ax,'Position'), 'XAxisLocation','top', ...
    'YAxisLocation','right','Color','none','XColor','k','YColor','none');
linkaxes([ax, top_ax],'x');

% Function to map mm -> ps labels
updateTopAxis = @() set(top_ax,'XTick',get(ax,'XTick'), ...
    'XTickLabel', arrayfun(@(mm) round(2*mm*1e-3/c*1e12,2), get(ax,'XTick'),'uni',0));
updateTopAxis();

%% ==========================================
%% 4. DATA COLLECTION LOOP
%% ==========================================
for k = 1:num_samples
    try
        % Read Position and Voltage
        positions(k) = queryNum(esp,"1TP?",3);
        voltages(k)  = s.inputSingleScan();
        
        % Update Plot
        set(hLine,'XData',positions(1:k),'YData',voltages(1:k));
        
        % Update Peak and Axis every 10th sample
        if mod(k,10)==0        
            updatePeak(positions, voltages, k, hPeak);
            % Add this line to auto-adjust limits as the stage moves
            axis(ax, 'tight');
            updateTopAxis();
        end
        drawnow limitrate;
        pause(sample_pause_s);
        
    catch
        break; % Stop loop if hardware errors or window closes
    end
end

% --- Stop Motion ---
try writeline(esp,"AB"); catch, end
fprintf('Acquisition complete. Analyzing data...\n');

%% ==========================================
%% 5. DATA ANALYSIS & GAUSSIAN FIT
%% ==========================================
valid = isfinite(positions) & isfinite(voltages);
pos = positions(valid);
vol = voltages(valid);

if isempty(pos)
    warning('No valid data collected.');
else
    % --- Binning (Average overlapping positions) ---
    nbins = 60; 
    edges = linspace(min(pos), max(pos), nbins+1);
    [~,~,bin] = histcounts(pos, edges);
    binCenters = 0.5*(edges(1:end-1)+edges(2:end));
    
    avgVol = nan(1,nbins);
    for i = 1:nbins
        idx = bin == i;
        if any(idx), avgVol(i) = mean(vol(idx)); end
    end
    
    % --- Prepare Fit Data ---
    % Convert Position (mm) to Delay (ps)
    % Delay = 2 * distance / speed_of_light
    time_ps = 2 * (binCenters * 1e-3) / c * 1e12; 
    
    validBins = isfinite(avgVol);
    x_fit = time_ps(validBins); x_fit = x_fit(:);
    y_fit = avgVol(validBins);  y_fit = y_fit(:);
    
    % --- Gaussian Fit ---
    % Model: A * exp( -(t - mu)^2 / (2*sigma^2) ) + Offset
    gauss_eq = @(b,x) b(1) .* exp(-(x - b(2)).^2 ./ (2*b(3).^2)) + b(4);
    
    % Initial Guesses
    [maxY, i0] = max(y_fit);
    minY   = min(y_fit);
    mu0    = x_fit(i0);
    sigma0 = (max(x_fit)-min(x_fit))/10; % Guess width is 10% of scan
    b0     = [maxY-minY, mu0, sigma0, minY];
    
    % Optimization
    opts = optimset('Display','off');
    if exist('lsqcurvefit','file')
        b_fit = lsqcurvefit(gauss_eq, b0, x_fit, y_fit, [], [], opts);
    else
        % Fallback if Optimization Toolbox is missing
        cost = @(b) sum((gauss_eq(b,x_fit) - y_fit).^2);
        b_fit = fminsearch(cost, b0, opts);
    end
    
    % --- Calculate Pulse Width ---
    sigma_ps   = abs(b_fit(3));
    FWHM_AC    = 2 * sqrt(2*log(2)) * sigma_ps;  % Autocorrelation FWHM
    FWHM_Pulse = FWHM_AC / sqrt(2);              % Actual Pulse FWHM (Gaussian assumption)
    
    % --- Plot Final Results ---
    figure('Name','Gaussian Fit Result','Color','w');
    plot(x_fit, y_fit, 'ko', 'MarkerFaceColor', [0.8 0.8 0.8], 'DisplayName', 'Raw Data'); hold on;
    
    t_smooth = linspace(min(x_fit), max(x_fit), 200);
    plot(t_smooth, gauss_eq(b_fit, t_smooth), 'b-', 'LineWidth', 2, 'DisplayName', 'Gaussian Fit');
    
    grid on; xlabel('Time Delay (ps)'); ylabel('Signal (V)');
    title(sprintf('Pulse Duration: %.3f ps (Gaussian)', FWHM_Pulse));
    legend('Location','best');

    % --- Save Results Beside This Script ---
    result_timestamp = datestr(now, 'yyyymmdd_HHMMSS');
    result_base = fullfile(script_dir, ['AutocorrelationResult_' result_timestamp]);
    result = struct( ...
        'positions_mm', pos, ...
        'voltages_V', vol, ...
        'time_ps', x_fit, ...
        'binned_signal_V', y_fit, ...
        'fit_parameters', b_fit, ...
        'sigma_ps', sigma_ps, ...
        'FWHM_autocorrelation_ps', FWHM_AC, ...
        'FWHM_pulse_ps', FWHM_Pulse);
    save([result_base '.mat'], 'result');
    writematrix([x_fit, y_fit], [result_base '.csv']);
    saveas(gcf, [result_base '.png']);
    
    % --- Print to Console ---
    fprintf('\n==================================\n');
    fprintf('       FIT RESULTS (Gaussian)     \n');
    fprintf('==================================\n');
    fprintf('Peak Position:      %.4f mm\n', (b_fit(2) * c / 2 * 1e-9));
    fprintf('Autocorrelation width: %.3f ps\n', FWHM_AC);
    fprintf('PULSE WIDTH:        %.3f ps\n', FWHM_Pulse);
    fprintf('Saved result files: %s.[mat/csv/png]\n', result_base);
    fprintf('==================================\n');
end

%% ==========================================
%% 6. HELPER FUNCTIONS
%% ==========================================
function s = queryStr(esp, cmd, tries)
    s = "";
    for t = 1:max(1,tries)
        try
            writeline(esp, cmd);
            s = strtrim(readline(esp));
            if ~isempty(s), return; end
        catch
            flush(esp); pause(0.005*t);
        end
    end
end

function v = queryNum(esp, cmd, tries)
    s = queryStr(esp, cmd, tries);
    v = str2double(s);
end

function tryRelease(sess)
    try, if ~isempty(sess) && isvalid(sess), release(sess); end, catch, end
end

function updatePeak(positions, vol, uptoK, hPeak)
    positions = positions(1:uptoK);
    vol = vol(1:uptoK);
    valid = isfinite(positions) & isfinite(vol);
    if ~any(valid), return; end
    vol(~valid) = -inf;
    [pv, idx] = max(vol);
    if isfinite(pv)
        set(hPeak, 'XData', positions(idx), 'YData', pv);
    end
end

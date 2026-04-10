clear; 
daqreset;                               
%% ==========================================
%% 1. USER PARAMETERS
%% ==========================================
center_mm      = 4.415;                 
span_mm        = 0.5;                   
acquisition_s  = 30.0;                  
sample_pause_s = 0.01;                  % Faster polling (100 Hz)
c              = 299792458;             

%% ==========================================
%% 2. HARDWARE SETUP
%% ==========================================
s  = daq.createSession('ni');
ai = addAnalogInputChannel(s,'Dev1','ai0','Voltage');
cleanupObj = onCleanup(@() tryRelease(s));

try
    esp = visadev("GPIB0::1::INSTR");
    configureTerminator(esp,"CR");
    esp.Timeout = 2.0;
    flush(esp);
    
    writeline(esp,"1MO");       
    % Set a very slow velocity to get 100nm resolution during a continuous move
    % Velocity = 0.01 mm/s means 100nm every 0.01 seconds
    writeline(esp,"1VA0.01"); 
    
    start_point = center_mm - (span_mm/2);
    end_point   = center_mm + (span_mm/2);
    
    fprintf('Moving to start point: %.4f mm\n', start_point);
    writeline(esp, sprintf("1PA%.4f", start_point));
    pause(20); 

    fprintf('Starting EX Scan05 (Continuous Scan)...\n');
    writeline(esp, "EX Scan05"); 
catch ME
    error('Hardware Init Failed: %s', ME.message);
end

%% ==========================================
%% 3. DATA COLLECTION LOOP
%% ==========================================
positions = nan(1,15000);
voltages  = nan(1,15000);
f = figure('Name','Knife-Edge Continuous Scan','Color','w');
ax = axes('Parent',f);
hLine = plot(ax, nan, nan, 'r.');
grid on; xlabel('Position (mm)'); ylabel('Power (V)');

tStart = tic; k = 1;
while toc(tStart) < acquisition_s
    positions(k) = queryNum(esp,"1TP?",3);
    voltages(k)  = s.inputSingleScan();
    
    if mod(k,20)==0
        set(hLine,'XData',positions(1:k),'YData',voltages(1:k));
        drawnow limitrate;
    end
    k = k + 1;
    pause(sample_pause_s);
end

writeline(esp, "AB"); 
pause(0.5);
writeline(esp, sprintf("1PA%.4f", start_point)); 

%% ==========================================
%% 4. ANALYSIS: ERF FIT (Forward Data Only)
%% ==========================================
valid = isfinite(positions) & isfinite(voltages);
p_raw = positions(valid);
v_raw = voltages(valid);

% Filter for Forward Scan only to remove hysteresis/backlash
direction = [0, diff(p_raw)];
forward_idx = direction > 0.00005; 
pos_fit = p_raw(forward_idx);
vol_fit = v_raw(forward_idx);

if isempty(pos_fit)
    error('No forward motion detected. Check Scan05 settings.');
end

% Direct ERF Model: b = [TotalPower, Center, Waist, Offset]
erf_model = @(b, x) (b(1)/2) * (1 + erf(sqrt(2)*(x - b(2))/b(3))) + b(4);
b0 = [max(vol_fit)-min(vol_fit), center_mm, 0.05, min(vol_fit)];

try
    [b_final, resnorm] = lsqcurvefit(erf_model, b0, pos_fit(:), vol_fit(:), [], [], optimset('Display','off'));
    beam_waist_um = abs(b_final(3)) * 1000;
    
    figure('Color','w');
    plot(pos_fit, vol_fit, 'k.', 'DisplayName', 'Forward Data'); hold on;
    plot(pos_fit, erf_model(b_final, pos_fit), 'r-', 'LineWidth', 2, 'DisplayName', 'ERF Fit');
    title(sprintf('Continuous Scan Fit | Waist = %.3f \\mum', beam_waist_um));
    xlabel('Position (mm)'); ylabel('Power (V)');
    legend; grid on;

    fprintf('\n--- FINAL SCAN RESULTS ---\n');
    fprintf('Beam Center:  %.4f mm\n', b_final(2));
    fprintf('Beam Waist:   %.3f um\n', beam_waist_um);
catch
    disp('Fit failed. Plotting raw forward data...');
    figure; plot(pos_fit, vol_fit); title('Forward Data (Fit Failed)');
end

%% ==========================================
%% 5. HELPER FUNCTIONS
%% ==========================================
function v = queryNum(esp, cmd, tries)
    v = nan;
    for t = 1:tries
        try
            writeline(esp, cmd);
            v = str2double(readline(esp));
            if ~isnan(v), return; end
        catch
            flush(esp);
        end
    end
end

function tryRelease(sess)
    try, if ~isempty(sess) && isvalid(sess), release(sess); end, catch, end
end
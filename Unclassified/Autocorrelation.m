clear;

daqreset;
%% --- User Parameters ---
num_scans = 1;               % Number of scans to average
start_pos = 24.1;           % mm
target_pos = 25.1;          % mm
step_size_um = 2;            % microns
step_size = step_size_um / 1000;  % mm
step_tolerance = 0.9;        % fraction of step to consider as moved
wait_per_step = 0.02;        % s between position checks
read_timeout_s = 0.030;      % 30 ms allowed read timeout

%% --- Setup DAQ ---
daq_session = daq.createSession('ni');
addAnalogInputChannel(daq_session, 'Dev1', 'ai5', 'Voltage');

%% --- Setup ESP300 via GPIB ---
esp = visadev("GPIB0::1::INSTR");
configureTerminator(esp, "CR");
esp.Timeout = 1.0;                % give headroom
flush(esp);                       % clear any stale bytes at start


% Motion parameters
writeline(esp, '1VA0.5');   % velocity
writeline(esp, '1AC0.5');   % acceleration
writeline(esp, '1AG0.5');   % deceleration
writeline(esp, '1FE100');  % max following error threshold

%% --- Move to start position before scanning ---
fprintf("Moving to START position: %.3f mm\n", start_pos);
writeline(esp, sprintf('1PA%.4f', start_pos));
pause(0.2);

% Wait until close to start
while true
    t0r = tic;
    try
        writeline(esp, '1PA?'); pause(0.05);
        pos = str2double(readline(esp));
    catch
        if toc(t0r) > read_timeout_s
            warning('Position read timeout (>30 ms) while moving to start. Retrying...');
            continue;
        end
    end
    if abs(pos - start_pos) < step_size
        break;
    end
end

%% --- Scan Grid ---
positions = start_pos:step_size:target_pos;
num_steps = numel(positions);
all_voltages = nan(num_scans, num_steps);   % use NaN for skipped points

%% --- Scans ---
for scan_idx = 1:num_scans
    fprintf("\n=== Starting Scan %d/%d ===\n", scan_idx, num_scans);

    % Reset to start each scan
    writeline(esp, sprintf('1PA%.4f', start_pos));
    pause(0.2);
    while true
        t0r = tic;
        try
            writeline(esp, '1PA?'); pause(0.1);
            pos = str2double(readline(esp));
        catch
            if toc(t0r) > read_timeout_s
                warning('Position read timeout (>30 ms) while resetting to start. Retrying...');
                continue;
            end
        end
        if abs(pos - start_pos) < step_size
            break;
        end
    end

    voltages = nan(1, num_steps);

    for k = 1:num_steps
        target = positions(k);

        if k > 1
            step_command = target - positions(k-1);
            writeline(esp, sprintf('1PR%.5f', step_command));

            % Wait until position change is detected (skip 1MD?)
            move_start = tic;
            reached = false;
            while toc(move_start) <= 10
                t0r = tic;
                try
                    writeline(esp, '1PA?'); pause(wait_per_step);
                    new_pos = str2double(readline(esp));
                catch
                    if toc(t0r) > read_timeout_s
                        warning('Position read timeout (>30 ms) at step %d. Skipping step...', k);
                        break; % break polling; this step will be NaN
                    else
                        continue; % quick error, keep trying
                    end
                end

                if abs(new_pos - pos) >= (abs(step_command) * step_tolerance)
                    pos = new_pos;
                    reached = true;
                    break;
                end
            end

            if ~reached
                warning('Position did not change enough at step %d. Skipping step...', k);
                % leave voltages(k) = NaN and continue to next target
                continue;
            end
        end

        % Read voltage
        voltages(k) = daq_session.inputSingleScan();

        fprintf('Scan %d, Step %3d/%3d: %.4f mm | V = %.4f V\n', ...
            scan_idx, k, num_steps, target, voltages(k));
    end

    all_voltages(scan_idx, :) = voltages;
end

%% --- Average across scans (ignore skipped NaNs) ---
% Use omitnan if available; fallback to nanmean for older versions
if verLessThan('matlab','9.1') %#ok<VERLESS>
    avg_voltages = nanmean(all_voltages, 1);  % Statistics Toolbox
else
    avg_voltages = mean(all_voltages, 1, 'omitnan');
end

%% --- Plot Results + Peak + Gaussian Fit ---
c = 299792458; % m/s
time_ps = 2 * positions * 1e-3 / c * 1e12;  % round-trip time in ps

figure;
ax1 = axes;
plot(ax1, positions, avg_voltages, 'r.-', 'LineWidth', 1.2);
xlabel(ax1, 'Position (mm)');
ylabel(ax1, 'DAQ Voltage (V)');
title(ax1, sprintf('Average of %d Scans', num_scans));
grid on; hold(ax1,'on');

% --- Peak marker (on averaged curve) ---
[peak_val, peak_idx] = max(avg_voltages);
peak_pos = positions(peak_idx);
plot(ax1, peak_pos, peak_val, 'ko', 'MarkerSize', 8, 'LineWidth', 1.5);
text(peak_pos, peak_val, sprintf('Peak: %.4f mm, %.4f V', peak_pos, peak_val), ...
    'VerticalAlignment','bottom','HorizontalAlignment','center','FontSize',9,'Color','k');

% --- Gaussian fit in time (ps), then convert to mm for overlay ---
valid = isfinite(avg_voltages);
x_fit = time_ps(valid);
y_fit = avg_voltages(valid);

% Gaussian: b = [A, mu, sigma, C]
gauss_eq = @(b,x) b(1) .* exp(-(x - b(2)).^2 ./ (2*b(3).^2)) + b(4);

[~, pk_i_fit] = max(y_fit);
center_guess = x_fit(pk_i_fit);
width_guess  = (max(x_fit) - min(x_fit)) / 10;
b0 = [max(y_fit), center_guess, width_guess, min(y_fit)];

b_fit = [];
if exist('lsqcurvefit','file')
    opts = optimset('Display','off');
    b_fit = lsqcurvefit(gauss_eq, b0, x_fit, y_fit, [], [], opts);
else
    % fallback using fminsearch
    opts = optimset('Display','off');
    b_fit = fminsearch(@(b) sum((gauss_eq(b, x_fit) - y_fit).^2), b0, opts);
end

t_fit = linspace(min(time_ps), max(time_ps), 800);
v_fit = gauss_eq(b_fit, t_fit);

% Convert ps -> mm for plotting
tfit_to_mm = t_fit * c / 2 * 1e-9;  % ps * (m/s)/2 * (mm/m) * (s/ps)
plot(ax1, tfit_to_mm, v_fit, 'b--', 'LineWidth', 1.4, 'DisplayName','Gaussian Fit');

% --- FWHM calculations (AC and single pulse) ---
fwhm_ac = 2 * sqrt(2 * log(2)) * abs(b_fit(3));   % in ps
single_pulse_fwhm = fwhm_ac / sqrt(2);            % in ps

% Annotate FWHM near the peak (at top axis units)
text_x = b_fit(2) * c / 2 * 1e-9;  % center in mm
text_y = peak_val + 0.02*range(y_fit);
annotation_str = sprintf('AC FWHM = %.2f ps\nPulse FWHM = %.2f ps', fwhm_ac, single_pulse_fwhm);
text(text_x, text_y, annotation_str, 'FontSize', 10, 'Color', 'b', 'HorizontalAlignment', 'center');

% Optional: draw vertical lines at mu ± FWHM/2 (convert to mm)
half = 0.5 * fwhm_ac;
x1_mm = (b_fit(2) - half) * c / 2 * 1e-9;
x2_mm = (b_fit(2) + half) * c / 2 * 1e-9;
yl = ylim(ax1);
plot(ax1, [x1_mm x1_mm], yl, 'b:', 'HandleVisibility','off');
plot(ax1, [x2_mm x2_mm], yl, 'b:', 'HandleVisibility','off');

legend(ax1, {'Averaged','Peak','Gaussian Fit'}, 'Location','best');

% --- Top axis for ps delay ---
top_ax = axes('Position', get(ax1, 'Position'), 'XAxisLocation', 'top', ...
              'YAxisLocation', 'right', 'Color', 'none', 'XColor', 'k', 'YColor', 'none');
set(top_ax, 'XLim', get(ax1, 'XLim'));
xticks_mm = get(ax1, 'XTick');
xticks_ps = 2 * xticks_mm * 1e-3 / c * 1e12;
set(top_ax, 'XTick', xticks_mm, 'XTickLabel', round(xticks_ps, 2));
xlabel(top_ax, 'Optical Delay Time (ps)');

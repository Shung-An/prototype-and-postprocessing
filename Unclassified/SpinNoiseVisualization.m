%% Final Plot: Correlated Spin Noise (Baseline Subtracted)
clear; clc; close all;

% --- 1. Load Data ---


% [file, path] = uigetfile('*.mat', 'Select your pos_diff_cumsum_clean.mat');

path = "D:\Quantum Squeezing Project\DataFiles\20260112_212409";
file = "pos_diff_cumsum_clean.mat";
if isequal(file,0), disp('User cancelled'); return; end
load(fullfile(path, file), 'result');
% --- 2. Configuration ---
targetLabel = '(3,2)-(8,7)'; 
mm_to_ps    = 6.6;           
manual_center_mm = 24.2;     
min_k       = 10;            
smooth_span = 5;             

% --- REFERENCE LINE SETTINGS (The Slope) ---
ref_slope = 0.18;    % Slope (uRad^2 per ps)
ref_x     = -40;     % Reference Time (ps)
ref_y     = -7;      % Reference Amplitude (uRad^2)

% --- 3. Extract Data for Target Pair ---
pairIdx = find(strcmp(result.labels, targetLabel));
if isempty(pairIdx), error('Label "%s" not found.', targetLabel); end

positions = result.bin_values;
nBins = numel(positions);
amps = nan(nBins, 1);

for b = 1:nBins
    v = result.cumsums{pairIdx}{b};
    if numel(v) >= min_k
        amps(b) = v(end) / numel(v); 
    end
end

valid = ~isnan(amps);
positions = positions(valid);
amps = amps(valid);

% --- 4. Process Data (Center, Trim, Sort) ---
t_ps = (positions - manual_center_mm) * mm_to_ps;
[t_sorted, sortIdx] = sort(t_ps);
y_sorted = amps(sortIdx);

% Trim 2 points from each end
if length(t_sorted) > 4
    t_plot = t_sorted(3:end-2);
    y_plot = y_sorted(3:end-2);
else
    t_plot = t_sorted;
    y_plot = y_sorted;
end

% --- 5. CALCULATE CONSTANT OFFSET (Previous Logic) ---
fprintf('Calculating Constant Offset... ');
try
    [fitResult, ~] = fit(t_plot, y_plot, 'fourier1');
    offset_val = fitResult.a0;
    fprintf('Fourier Fit Found: %.4f\n', offset_val);
catch
    offset_val = mean(y_plot);
    fprintf('Fit failed, using Mean: %.4f\n', offset_val);
end

% --- 6. CALCULATE & SUBTRACT (Guideline + Offset) ---
fprintf('Subtracting Guideline (Slope=%.2f) + Offset (%.2f)\n', ref_slope, offset_val);

% 1. Calculate the Linear Guideline values for every point
linear_baseline = ref_slope .* (t_plot - ref_x) + ref_y;

% 2. Subtract BOTH the Linear Guideline AND the Constant Offset
y_plot_corrected = y_plot - linear_baseline - offset_val;

% 3. Apply smoothing
y_smooth = smooth(t_plot, y_plot_corrected, smooth_span, 'moving'); 

% --- 7. Generate Publication Plot ---
width_inch = 6; 
height_inch = 4.5;
fig = figure('Units', 'Inches', 'Position', [1, 1, width_inch, height_inch], ...
             'Color', 'w', 'Name', 'Correlated Spin Noise Final');
ax = gca;
hold(ax, 'on');

% A. Plot Zero Line (Reference)
yline(ax, 0, '--', 'Color', [0.5 0.5 0.5], 'LineWidth', 1.5, ...
    'DisplayName', 'Zero Reference');

% B. Plot Corrected Data (Scatter)
s1 = scatter(t_plot, y_plot_corrected, 30, ...
    'MarkerFaceColor', [0.7 0.75 0.85], ... 
    'MarkerEdgeColor', [0.4 0.5 0.7], ...   
    'MarkerFaceAlpha', 0.6, ...             
    'LineWidth', 0.5, ...
    'DisplayName', 'Raw Data (Corr.)');

% C. Plot Smoothed Curve
p1 = plot(t_plot, y_smooth, '-', ...
    'Color', [0 0.2 0.6], ... 
    'LineWidth', 2, ...
    'DisplayName', 'Smoothed Trace');

% --- 8. Formal Formatting ---
set(ax, 'FontName', 'Arial', 'FontSize', 12, 'LineWidth', 1.2);
set(ax, 'TickDir', 'out', 'Box', 'on'); 
set(ax, 'XMinorTick', 'on', 'YMinorTick', 'on');

% Labels
xlabel('Delay Time \Delta\it{t} \rm(ps)', 'Interpreter', 'tex', 'FontSize', 13, 'FontWeight', 'bold');
ylabel('Correlated Spin Noise Amplitude (\mu rad^2)', 'Interpreter', 'tex', 'FontSize', 13,  'FontWeight', 'bold');

% Grid
grid on;
ax.GridAlpha = 0.15; 

% Limits (Auto-scale)
xlim([min(t_plot)-10, max(t_plot)+10]);
y_max = max(abs(y_plot_corrected));
ylim([-y_max*1.2, y_max*1.2]); % Symmetric Y-axis

hold off;
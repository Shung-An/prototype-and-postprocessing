%% Presentation-Ready Log-Log (Specific Folder)
clear; clc; close all;

% --- 1. Load Data ---
% Set the specific target folder
targetFolder = 'D:\Quantum Squeezing Project\DataFiles\20260112_212409';

if isfolder(targetFolder)
    startPath = fullfile(targetFolder, '*.mat');
else
    warning('Folder not found. Opening current directory.');
    startPath = '*.mat';
end

[file, path] = uigetfile(startPath, 'Select pos_diff_cumsum_clean.mat');
if isequal(file,0), disp('User cancelled'); return; end
load(fullfile(path, file), 'result');

% --- 2. Configuration ---
targetLabel = '(3,2)-(8,7)'; 
offset_val  = 42.221583;    
frame_dt_s  = 0.1;          
manual_center_mm = 24.2;    
mm_to_ps    = 6.6;          
targets_ps  = [0, -10];     

% Horizontal Line Settings
h_line_val  = 10.0;          
h_line_start = 10.0;         
h_line_text = 'Spin Noise Level'; 

% Text Placement Control
text_x_location = 14000;  
electronic_text = 'Electronic limit'; 

% --- 3. Extract Data ---
pairIdx = find(strcmp(result.labels, targetLabel));
if isempty(pairIdx), error('Label not found.'); end

binVals_mm = result.bin_values;       
cumsums    = result.cumsums{pairIdx};
binVals_ps = (binVals_mm - manual_center_mm) * mm_to_ps;

% --- 4. Setup Figure Aesthetics ---
% DATA COLORS
color0  = [0 0.2 0.6];      % Navy Blue (Data Trace)
color10 = [0.8 0.1 0.1];    % Deep Red  (Data Trace)

% DASH LINE COLORS (Distinct from Data)
color0_dash  = [0.2 0.6 1.0]; % Brighter/Sky Blue (for Horizontal Line)
color10_dash = [0.9 0.4 0.1]; % Orange-Red (for Slope Line)

f = figure('Color','w', 'Units','pixels', 'Position',[100 100 1000 700], ...
           'Name', 'Convergence Presentation');
ax = axes(f);
hold(ax, 'on');
fprintf('\n--- Generating Presentation Plot ---\n');

maxY = -inf;

% --- 5. Plotting Loop ---
for i = 1:length(targets_ps)
    t_target = targets_ps(i);
    [~, idx] = min(abs(binVals_ps - t_target));
    
    actual_ps = binVals_ps(idx);
    v = cumsums{idx};
    
    if isempty(v), continue; end
    nFrames = numel(v);
    
    % Calculation
    running_avg = v ./ (1:nFrames)'; 
    y_diff = abs(running_avg - offset_val);
    y_diff(y_diff <= 0) = 1e-20; 
    
    t_plot = (1:nFrames)' * frame_dt_s;
    maxY = max(maxY, max(y_diff));
    
    % Style
    if i == 1
        lineColor = color0;
        displayName = sprintf('Time Zero (0 ps)');
    else
        lineColor = color10;
        displayName = sprintf('Offset Time (-10 ps)');
    end
    
    % PLOT Data
    loglog(ax, t_plot, y_diff, '-', ...
        'Color', lineColor, ...
        'LineWidth', 2.5, ...
        'DisplayName', displayName);
end

% --- 6. Add Theoretical Slope (1/sqrt(t)) ---
ref_t = logspace(log10(frame_dt_s), log10(max(t_plot)), 100);
A = 50; 
ref_y = A ./ sqrt(ref_t); 

% Plot slope with Distinct Red-ish Color
% loglog(ax, ref_t, ref_y, '--', ...
%     'Color', color10_dash, ...  % <--- CHANGED to Distinct Color
%     'LineWidth', 4, ...
%     'HandleVisibility', 'off'); 

% --- 7. Arbitrary Text Placement ---
text_y_location = A / sqrt(text_x_location);

% text(ax, text_x_location, text_y_location, ['  ' electronic_text], ...
%     'Color', color10_dash, ...  % <--- Matches the distinct dash line
%     'FontSize', 14, ...
%     'FontName', 'Arial', ...
%     'VerticalAlignment', 'top', ...  
%     'HorizontalAlignment', 'right');

% --- 8. Add Custom Horizontal Dashed Line (Starts at 10s) ---
x_line_ends = [h_line_start, max(t_plot)];
y_line_ends = [h_line_val, h_line_val];

% Plot Horizontal line with Distinct Blue-ish Color
% loglog(ax, x_line_ends, y_line_ends, '--', ...
%     'Color', color0_dash, ...   % <--- CHANGED to Distinct Color
%     'LineWidth', 4, ...
%     'HandleVisibility', 'off'); 

% Add the text label
% text(ax, max(t_plot), h_line_val, h_line_text, ...
%     'Color', color0_dash, ...   % <--- Matches the distinct dash line
%     'FontSize', 14, ...
%     'FontName', 'Arial', ...
%     'VerticalAlignment', 'bottom', ...   
%     'HorizontalAlignment', 'right');     

% --- 9. Formal Styling ---
set(ax, 'FontSize', 14, 'FontName', 'Arial', 'LineWidth', 1.5);
set(ax, 'XScale', 'log', 'YScale', 'log');

% Grids
grid(ax, 'on'); 
grid(ax, 'minor');
ax.GridAlpha = 0.3;      
ax.MinorGridAlpha = 0.15; 

% Labels
xlabel(ax, 'Integration Time (s)', 'FontWeight', 'bold');
ylabel(ax, 'Correlated Spin Noise Amplitude (\mu rad^2)', 'FontWeight', 'bold');
% title(ax, 'Spin Noise Amplitude from Sm_{0.7}Er_{0.3}FeO_3', 'FontWeight', 'bold');

% Legend
lgd = legend(ax, 'Location', 'northeast');
set(lgd, 'FontSize', 12, 'Box', 'on');

% Limits
currentYMax = max(maxY, max(ref_y)); 
ylim(ax, [0.1, currentYMax * 1.5]); 
xlim(ax, [frame_dt_s, max(t_plot)*1.1]); 

hold off;
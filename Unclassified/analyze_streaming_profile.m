function analyze_streaming_profile(target_folder)
% =========================================================================
% STREAMING PROFILE ANALYZER
% Parses profile.txt to analyze system latency, processing time, and stability.
%
% Visualizations:
% 1. Timeline: Processing times vs. Wall Clock Time.
% 2. Histograms: Distribution of processing times (Stability check).
% =========================================================================

%% 1. Select Folder & File
if nargin < 1
    startPath = 'Z:\Quantum Squeezing Project\DataFiles';
    if ~isfolder(startPath), startPath = pwd; end
    runFolder = uigetdir(startPath, 'Select Data Folder containing profile.txt');
    if runFolder == 0, return; end
else
    runFolder = target_folder;
end

fProfile = fullfile(runFolder, 'profile.txt');
if ~isfile(fProfile)
    error('profile.txt not found in %s', runFolder);
end

%% 2. Parse Data
fprintf('Reading profile.txt...\n');
txt = fileread(fProfile);

% Regex to capture: 1.Timestamp, 2.OneStep, 3.Transfer, 4.GPU
% Pattern based on: "Transfer start timestamp: 14:15:20.497 ,One Step Time: 4.96 ms, Transfer and process Time: 4.95 ms, GPU Process Time: 0.00 ms"
pattern = 'timestamp:\s*(\d{2}:\d{2}:\d{2}\.\d+)\s*,One Step Time:\s*([\d\.]+)\s*ms,\s*Transfer.*?Time:\s*([\d\.]+)\s*ms,\s*GPU.*?Time:\s*([\d\.]+)\s*ms';

tokens = regexp(txt, pattern, 'tokens');

if isempty(tokens)
    error('Could not parse data. Check if log format has changed.');
end

% Convert to Matrix
N = numel(tokens);
fprintf('Parsed %d log entries.\n', N);

timestamps_str = cell(N,1);
data_metrics   = zeros(N,3); % Col 1: OneStep, Col 2: Transfer, Col 3: GPU

for i = 1:N
    timestamps_str{i} = tokens{i}{1};
    data_metrics(i,1) = str2double(tokens{i}{2}); % One Step
    data_metrics(i,2) = str2double(tokens{i}{3}); % Transfer
    data_metrics(i,3) = str2double(tokens{i}{4}); % GPU
end

% Convert timestamps to relative seconds
try
    t_abs = datetime(timestamps_str, 'InputFormat', 'HH:mm:ss.SSS');
catch
    t_abs = datetime(timestamps_str, 'InputFormat', 'HH:mm:ss.SSSSSS'); % Handle microsec if present
end

% Handle day rollover if necessary (though unlikely for short logs)
t_dur = t_abs - t_abs(1);
t_sec = seconds(t_dur);

%% 3. Calculate Statistics
stats_names = {'One Step (Total)', 'Transfer & Process', 'GPU Process'};
fprintf('\n================ PROFILE STATISTICS ================\n');
fprintf('%-20s | %-8s | %-8s | %-8s | %-8s\n', 'Metric', 'Mean', 'Median', 'Max', 'StdDev');
fprintf('------------------------------------------------------------\n');

for i = 1:3
    d = data_metrics(:,i);
    fprintf('%-20s | %6.2fms | %6.2fms | %6.2fms | %6.2fms\n', ...
        stats_names{i}, mean(d), median(d), max(d), std(d));
end

% Calculate Loop Jitter (Difference between start timestamps)
if N > 1
    dt_loop = diff(t_sec) * 1000; % ms
    fprintf('------------------------------------------------------------\n');
    fprintf('%-20s | %6.2fms | %6.2fms | %6.2fms | %6.2fms\n', ...
        'Loop Cycle Jitter', mean(dt_loop), median(dt_loop), max(dt_loop), std(dt_loop));
end
fprintf('====================================================\n');

%% 4. PLOT 1: Timeline Analysis
f1 = figure('Name', 'Profile Timeline', 'Color', 'w', 'Position', [100 100 1200 600]);

subplot(2,1,1);
plot(t_sec, data_metrics(:,1), 'LineWidth', 1.0, 'Color', [0 0.4470 0.7410]); hold on;
plot(t_sec, data_metrics(:,3), 'LineWidth', 1.0, 'Color', [0.8500 0.3250 0.0980]);
grid on;
ylabel('Time (ms)');
title('Processing Time per Frame');
legend('Total Step Time', 'GPU Time', 'Location', 'best');
xlim([min(t_sec) max(t_sec)]);

% Highlight spikes
spike_thresh = mean(data_metrics(:,1)) + 3*std(data_metrics(:,1));
yline(spike_thresh, '--r', '3\sigma Spike Threshold');

subplot(2,1,2);
if N > 1
    plot(t_sec(2:end), dt_loop, '.-', 'Color', [0.4660 0.6740 0.1880]);
    grid on;
    ylabel('Interval (ms)');
    xlabel('Experiment Time (s)');
    title('Frame Arrival Interval (Jitter)');
    yline(mean(dt_loop), 'k-', sprintf('Avg: %.1fms', mean(dt_loop)));
end

saveas(f1, fullfile(runFolder, 'profile_timeline.png'));

%% 5. PLOT 2: Distribution Histograms
f2 = figure('Name', 'Profile Distributions', 'Color', 'w', 'Position', [150 150 1200 400]);
tiledlayout(1,3, 'Padding', 'compact');

titles = {'Total Step Time', 'Transfer Time', 'GPU Time'};
colors = {'b', 'm', 'r'};

for i = 1:3
    nexttile;
    histogram(data_metrics(:,i), 50, 'FaceColor', colors{i});
    grid on;
    xlabel('Time (ms)'); ylabel('Count');
    title(titles{i});
    subtitle(sprintf('Mean: %.2f ms', mean(data_metrics(:,i))));
end

saveas(f2, fullfile(runFolder, 'profile_histograms.png'));

end
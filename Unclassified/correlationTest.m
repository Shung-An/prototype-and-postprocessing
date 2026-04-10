%% Parameters
rows_per_segment = 16;
correlation_window = 8;

%% Data Reshaping
A = data(1,:);
B = data(2,:);

% Ensure data length is divisible by rows_per_segment
A_trimmed = A(1:end-mod(length(A), rows_per_segment));
B_trimmed = B(1:end-mod(length(B), rows_per_segment));

% Reshape data into matrices
A_reshaped = reshape(A_trimmed, rows_per_segment, []);
B_reshaped = reshape(B_trimmed, rows_per_segment, []);

%% GPU Acceleration Setup
A_gpu = gpuArray(A_reshaped);
B_gpu = gpuArray(B_reshaped);

%% Correlation Calculation (GPU-accelerated)
corr = zeros(correlation_window, correlation_window, rows_per_segment, 'gpuArray');

for m = 1:correlation_window
    for k = 1:correlation_window
        A_diff = A_gpu(m, :) - A_gpu(m+correlation_window, :);
        B_diff = B_gpu(k, :) - B_gpu(k+correlation_window, :);
        
        for n = 1:rows_per_segment
            A_slice = A_diff(n:rows_per_segment:end);
            B_slice = B_diff(n:rows_per_segment:end);
            corr(m, k, n) = sum(A_slice .* B_slice) / (length(A_reshaped) / rows_per_segment);
        end
    end
end

% Transfer results back to CPU
corr = gather(corr);

%% Slice Selection
remove_indices = [2, 8, 10, 11, 13];
keep_indices = setdiff(1:size(corr, 3), remove_indices);
reduced_corr = corr(:, :, keep_indices);

%% Create Figure with Subplots
figure('Name', 'Correlation Analysis Results', 'NumberTitle', 'off', 'Position', [100, 100, 1920, 1200], 'Visible', 'off');

% %% Amplitude Variation Plot
% subplot(2, 2, [1, 3]);
% coordinates = {[1, 2], [1, 3], [1, 4], [2, 1], [3, 1], [4, 1]};
% hold on;
% 
% for i = 1:length(coordinates)
%     x = coordinates{i}(1);
%     y = coordinates{i}(2);
%     amplitude_values = abs(squeeze(corr(x, y, :)));
%     semilogy(1:length(amplitude_values), amplitude_values, 'o-', 'LineWidth', 1.5, ...
%              'DisplayName', sprintf('(A, B) = (%d, %d)', x, y));
% end
% 
% hold off;
% xlabel('Index');
% ylabel('Amplitude (log scale)');
% title('Amplitude Variation for Specified Coordinates');
% legend('Location', 'best');
% grid on;
% 
% %% Full Correlation Heatmap
% subplot(2, 2, 2);
% mean_values = mean(corr, 3);
% h_full = heatmap(mean_values);
% h_full.Colormap = parula;
% title('Mean of Full Correlation');
% xlabel('Channel B');
% ylabel('Channel A');
% % display(mean_values);
% % Custom labels for better readability
% h_full.XDisplayLabels = arrayfun(@(x) sprintf('B_{%d}-B_{%d}', x, x+correlation_window), 1:correlation_window, 'UniformOutput', false);
% h_full.YDisplayLabels = arrayfun(@(x) sprintf('A_{%d}-A_{%d}', x, x+correlation_window), 1:correlation_window, 'UniformOutput', false);
% 
% %% Reduced Correlation Heatmap
% subplot(2, 2, 4);
% mean_reduced_values = mean(reduced_corr, 3);
% h_reduced = heatmap(mean_reduced_values);
% h_reduced.Colormap = parula;
% title('Mean of Reduced Correlation');
% xlabel('Channel B');
% ylabel('Channel A');
% 
% % Custom labels for better readability
% h_reduced.XDisplayLabels = arrayfun(@(x) sprintf('B_{%d}-B_{%d}', x, x+correlation_window), 1:correlation_window, 'UniformOutput', false);
% h_reduced.YDisplayLabels = arrayfun(@(x) sprintf('A_{%d}-A_{%d}', x, x+correlation_window), 1:correlation_window, 'UniformOutput', false);


%% Plot the Full Correlation Heatmap
subplot(2, 1, 1);
mean_values = mean(corr, 3);
h_full = heatmap(mean_values);
h_full.Colormap = parula;
title('Mean of Full Correlation');
xlabel('Channel B');
ylabel('Channel A');

% Custom labels for better readability
h_full.XDisplayLabels = arrayfun(@(x) sprintf('B_{%d}-B_{%d}', x, x+correlation_window), 1:correlation_window, 'UniformOutput', false);
h_full.YDisplayLabels = arrayfun(@(x) sprintf('A_{%d}-A_{%d}', x, x+correlation_window), 1:correlation_window, 'UniformOutput', false);

%% Plot first 10 cycles of A and B channels
subplot(2, 1, 2);
cycles_to_plot = 10;
samples_per_cycle = rows_per_segment;
total_samples = cycles_to_plot * samples_per_cycle;

plot(1:total_samples, A(1:total_samples), 'b-', 'DisplayName', 'Channel A');
hold on;
plot(1:total_samples, B(1:total_samples), 'r-', 'DisplayName', 'Channel B');
hold off;

xlabel('Sample');
ylabel('Amplitude');
title(sprintf('First %d Cycles of Channels A and B', cycles_to_plot));
legend('Location', 'best');
grid on;

%% Adjust layout
sgtitle('Correlation Analysis Results');

%% Save Figure with Date and Time
current_time = datetime('now');
formatted_time = datestr(current_time, 'yyyy-mm-dd_HH-MM-SS'); % Format: YYYY-MM-DD_HH-MM-SS
figure_filename = sprintf('Correlation_Analysis_%s.png', formatted_time);
% Specify the directory where you want to save the figure
save_directory = 'C:\Program Files (x86)\Gage\CompuScope\CompuScope C SDK\Test\Correlation results\';

% Combine the directory and filename
full_path = fullfile(save_directory, figure_filename);
saveas(gcf, full_path);
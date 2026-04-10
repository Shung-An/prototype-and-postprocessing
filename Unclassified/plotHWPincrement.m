
% Reshape the 8x8x41 matrix into a 64x41 matrix
reshaped_data = reshape(mean_values_elapse, 64, 40);

% Use the first frame as baseline and subtract it from all frames
% baseline = reshaped_data(:, 1);
% relative_data = reshaped_data(:, 2:end) - repmat(baseline, 1, 40);
relative_data = reshaped_data;
% Create a figure
figure('Visible','off','Position', [100, 100, 1400, 900]);  % Adjusted width for legend

% Set up colors for the lines (8 colors for 8 rows)
colors = jet(8);  % Create 8 distinct colors

% Create 8 subplots, one for each column (A1-A8, A2-A9, etc.)
plotHandles = gobjects(8, 1);  % To store plot handles for legend

for col = 1:8
    subplot(4, 2, col);
    hold on;
    
    % Plot 8 lines for each row in this column
    for row = 1:8
        % Calculate the index for the corresponding row and column
        index = row + (col - 1) * 8;
        h = plot(linspace(setPosition2*0.00572958,(setPosition2+frames*stepSize2)*0.00572958,frames), relative_data(index, :), 'Color', colors(row, :), 'LineWidth', 1.5);
        if col == 1
            plotHandles(row) = h;  % Store only the first column's handles for legend
        end
    end
    
    % Customize each subplot
    xlabel('HWP degrees change (relative to balanced condition)');
    ylabel('Relative Mean Value (V^2)');
    title(sprintf('A%d - A%d', col, col +8));  % Title for each subplot
    grid on;
    
    % Add a zero line to show the baseline reference
    yline(0, 'k--', 'LineWidth', 1);
    
    % Adjust y-axis limits to be symmetric around zero
    ylim_max = max(abs(ylim));
    ylim([-ylim_max, ylim_max]);
    
    hold off;
end

% Create a single legend for the entire figure
legend_labels = cell(8, 1);
for i = 1:8
    legend_labels{i} = sprintf('B_{%d}-B_{%d}', i, i+8);
end
legend(plotHandles, legend_labels, 'Location', 'eastoutside', 'Orientation', 'vertical');

% Add an overall title
sgtitle('Relative Changes Across 40 Frames for Correlation Measurements.', 'FontSize', 16);


% Adjust subplot layout
set(gcf, 'Units', 'normalized');
% Save the figure as an image file (e.g., PNG)
saveas(gcf, 'relative_changes_plot.png');  % Save as PNG
% Alternatively, you can use exportgraphics(gcf, 'relative_changes_plot.png');

% Close the figure to avoid displaying it
close(gcf);


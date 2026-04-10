

% Example usage:
fs=2623/64/2;


% Call the function
[tau, adev] = calculate_allan_variance_multichannel(convert_3rd_seq_t, fs);

function [tau, adev] = calculate_allan_variance_multichannel(omega, Fs)
    % Calculate Allan variance and deviation for multiple channels
    % Inputs:
    %   omega: Input time series data (N x 64 matrix)
    %   Fs: Sampling frequency in Hz
    % Outputs:
    %   tau: Averaging time
    %   adev: Allan deviation (matrix with 64 columns)

    % Set up tau values
    maxTau = floor(size(omega, 1)/2);
    m = logspace(0, floor(log10(maxTau)), 100);
    m = unique(round(m)); % Ensure unique integer values
    
    % Initialize adev matrix
    adev = zeros(length(m), size(omega, 2));
    
    % Calculate Allan variance for each channel
    for channel = 1:size(omega, 2)
        [avar, tau] = allanvar(omega(:, channel), m, Fs);
        adev(:, channel) = sqrt(avar);
    end
    
    % Plot results using loglog
    figure;
    hold on;
    colors = jet(size(omega, 2)); % Create a colormap for 64 channels
    
    for channel = 1:size(omega, 2)
        loglog(tau, adev(:, channel), 'Color', colors(channel, :), 'LineWidth', 1);
    end
    
    grid on;
    xlabel('Averaging Time \tau (s)');
    ylabel('Allan Deviation \sigma(\tau) (V^2)');
    title('Allan Deviation Plot for 64 Channels (Log-Log Scale)');
    
    % Create a colorbar to show channel numbers
    colormap(colors);
    c = colorbar;
    c.Label.String = 'Channel';
    c.Ticks = linspace(0, 1, 5); % 5 ticks on the colorbar
    c.TickLabels = {'1', '16', '32', '48', '64'}; % Label the ticks
    
    % Set axes to log scale
    set(gca, 'XScale', 'log', 'YScale', 'log');
    
    hold off;
    
    % Optional: Add characteristic slopes for noise identification
    hold on;
    tau_range = logspace(log10(min(tau)), log10(max(tau)), 100);
    
    % Angle Random Walk (slope = -1/2)
    loglog(tau_range, 1e-8 * tau_range.^(-0.5), 'k--', 'LineWidth', 1);
    text(tau_range(end), 1e-8 * tau_range(end)^(-0.5), 'ARW', 'VerticalAlignment', 'top');
    
    % Bias Instability (slope = 0)
    loglog(tau_range, 1e-9 * ones(size(tau_range)), 'k--', 'LineWidth', 1);
    text(tau_range(end), 1e-9, 'BI', 'VerticalAlignment', 'bottom');
    
    % Rate Random Walk (slope = 1/2)
    loglog(tau_range, 1e-10 * tau_range.^(0.5), 'k--', 'LineWidth', 1);
    text(tau_range(end), 1e-10 * tau_range(end)^(0.5), 'RRW', 'VerticalAlignment', 'bottom');
    
    legend('off');
    hold off;
end
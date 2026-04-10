function eigenmode_demo()
    % --- 1. GENERATE FAKE DATA ---
    % 1000 frames, 8x8 pixels (64 pixels total)
    n_frames = 1000;
    n_pixels = 64;
    
    % Background: Random Shot Noise (Gaussian)
    X = randn(n_frames, n_pixels);
    
    % Interference: Add a diagonal stripe to random frames
    stripe_pattern = eye(8); % 8x8 diagonal identity matrix
    stripe_vector = stripe_pattern(:)'; % Flatten to 1x64
    
    % Add the stripe to 10% of frames with random intensity
    for i = 1:n_frames
        if rand > 0.9
            intensity = 5 * rand; % Variable brightness
            X(i, :) = X(i, :) + (intensity * stripe_vector);
        end
    end
    
    % --- 2. THE ALGORITHM (Step-by-Step) ---
    
    % Step A: Center the data
    mean_frame = mean(X, 1);
    X_centered = X - mean_frame;
    
    % Step B: Calculate Covariance Matrix (64x64)
    % This tells us how pixel i correlates with pixel j
    CovMatrix = cov(X_centered);
    
    % Step C: Eigen Decomposition
    % V = Eigenvectors (Columns are the modes)
    % D = Eigenvalues (Diagonal matrix)
    [V, D] = eig(CovMatrix);
    
    % Step D: Sort by Energy (High to Low)
    eigenvalues = diag(D);
    [eigenvalues, sortIdx] = sort(eigenvalues, 'descend');
    eigenvectors = V(:, sortIdx);
    
    % --- 3. VISUALIZATION ---
    figure('Color','w', 'Position', [100 100 1000 400]);
    
    % Plot Mode 1 (Should be the Stripe)
    subplot(1,3,1);
    mode1_img = reshape(eigenvectors(:,1), [8, 8]);
    imagesc(mode1_img); colormap jet; title('Eigenmode 1 (Dominant)');
    axis square;
    
    % Plot Mode 2 (Should be Noise)
    subplot(1,3,2);
    mode2_img = reshape(eigenvectors(:,2), [8, 8]);
    imagesc(mode2_img); colormap jet; title('Eigenmode 2 (Noise)');
    axis square;
    
    % Plot Energies (Scree Plot)
    subplot(1,3,3);
    plot(eigenvalues, '-o', 'LineWidth', 2);
    grid on; title('Eigenvalues (Energy)');
    xlabel('Mode Number'); ylabel('Variance');
end
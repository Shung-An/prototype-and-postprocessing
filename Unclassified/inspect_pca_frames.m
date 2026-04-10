function inspect_pca_frames(target_folder)
% =========================================================================
% INSPECT PCA FRAMES
% This script plays a "Video" of the frames rejected by the PCA filter.
% It helps you visually confirm that the "Bad" frames actually contain stripes.
% =========================================================================

%% 1. Select Folder
if nargin < 1
    startPath = 'Z:\Quantum Squeezing Project\DataFiles';
    if ~isfolder(startPath), startPath = pwd; end
    runFolder = uigetdir(startPath, 'Select Data Folder to Inspect');
else
    runFolder = target_folder;
end

fCM = fullfile(runFolder,'cm.bin');
assert(isfile(fCM), 'cm.bin not found.');

%% 2. Load and Prep Data
fprintf('Loading data...\n');
fid = fopen(fCM,'rb'); raw = fread(fid,'double'); fclose(fid);
cm = reshape(raw, 64, []).';
N = size(cm, 1);

% Filter saturated pixels first (same as pipeline)
ch11 = sub2ind([8 8],1,1);
cm = cm(cm(:,ch11) <= 1e-6, :); 

%% 3. Run PCA Detection
fprintf('Running PCA detection...\n');
[~, score, ~, ~, ~] = pca(cm);

% Calculate "Stripeness" (Magnitude of Mode 1)
noise_magnitude = sqrt(score(:, 1).^2);

% Define Cutoff (Same as pipeline: Sigma = 1.5)
pca_sigma_cutoff = 1.5;
med_val = median(noise_magnitude);
mad_val = median(abs(noise_magnitude - med_val));
cutoff  = med_val + (pca_sigma_cutoff * mad_val * 1.4826); 

% Find indices
bad_indices  = find(noise_magnitude > cutoff);
good_indices = find(noise_magnitude <= cutoff);

fprintf('Found %d BAD frames and %d GOOD frames.\n', numel(bad_indices), numel(good_indices));

%% 4. PLAYBACK: The Worst Offenders
% Sort bad frames by "Loudness" so you see the strongest stripes first
[~, sortIdx] = sort(noise_magnitude(bad_indices), 'descend');
sorted_bad_indices = bad_indices(sortIdx);

frames_to_show = min(100, numel(sorted_bad_indices)); % Show top 100 bad frames

f = figure('Name', 'Frame Inspector', 'Color', 'w', 'Position', [100 100 600 600]);

% --- PLAY BAD FRAMES ---
fprintf('\nPlaying the top %d REJECTED frames (Press Ctrl+C to stop)...\n', frames_to_show);
for i = 1:frames_to_show
    idx = sorted_bad_indices(i);
    frame_data = reshape(cm(idx, :), [8, 8]);
    
    if ~isvalid(f), break; end % Stop if user closes window
    
    imagesc(frame_data);
    colormap jet; 
    colorbar;
    caxis([-1e-7 1e-7]); % Fixed scale to compare easily
    axis square; axis off;
    
    title(sprintf('REJECTED FRAME %d / %d\nStripe Score: %.2f (Cutoff: %.2f)', ...
        i, frames_to_show, noise_magnitude(idx), cutoff), 'Color', 'r', 'FontSize', 14);
    
    pause(0.1); % Adjust speed here (0.1 = 10 fps)
end

%% 5. PLAYBACK: Random Good Frames
% Show some good ones to compare
fprintf('\nPlaying 50 KEPT frames for comparison...\n');
random_good = good_indices(randperm(numel(good_indices), min(500, numel(good_indices))));

for i = 1:numel(random_good)
    idx = random_good(i);
    frame_data = reshape(cm(idx, :), [8, 8]);
    
    if ~isvalid(f), break; end
    
    imagesc(frame_data);
    colormap jet; 
    colorbar;
    caxis([-1e-7 1e-7]); 
    axis square; axis off;
    
    title(sprintf('KEPT FRAME (Clean) %d\nStripe Score: %.2f', ...
        i, noise_magnitude(idx)), 'Color', 'g', 'FontSize', 14);
    
    pause(0.1);
end

fprintf('Done.\n');
end
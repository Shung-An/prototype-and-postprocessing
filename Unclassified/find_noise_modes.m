function find_noise_modes(target_folder)
% =========================================================================
% MODE FINDER
% Helps identify which PCA Component corresponds to the "Stripe" noise.
% =========================================================================

%% 1. Select Folder
if nargin < 1
    startPath = 'Z:\Quantum Squeezing Project\DataFiles';
    if ~isfolder(startPath), startPath = pwd; end
    runFolder = uigetdir(startPath, 'Select Data Folder');
else
    runFolder = target_folder;
end

fCM = fullfile(runFolder,'cm.bin');
assert(isfile(fCM), 'cm.bin not found.');

%% 2. Load Data
fprintf('Loading data...\n');
fid = fopen(fCM,'rb'); raw = fread(fid,'double'); fclose(fid);
cm = reshape(raw, 64, []).';

% Remove saturation (ch11 > 1e-6) to see real patterns
ch11 = sub2ind([8 8],1,1);
cm = cm(cm(:,ch11) <= 1e-6, :); 

%% 3. Run PCA
fprintf('Calculating Eigenmodes...\n');
[coeff, ~, ~, ~, explained] = pca(cm);

%% 4. Plot Top 9 Modes
f = figure('Name', 'Top 9 Eigenmodes', 'Color', 'w', 'Position', [50 50 1000 900]);
tiledlayout(3,3, 'TileSpacing', 'compact');

for i = 1:9
    nexttile;
    % Reshape the 64-element vector into 8x8 image
    mode_img = reshape(coeff(:, i), [8, 8]);
    
    imagesc(mode_img);
    colormap jet; 
    axis square; axis off;
    title(sprintf('Mode %d (%.1f%% Var)', i, explained(i)), 'FontSize', 12, 'FontWeight', 'bold');
end

sgtitle('Look for the "Stripe" pattern here. Which Mode # is it?', 'FontSize', 16);
fprintf('Done. Check the figure window.\n');
end
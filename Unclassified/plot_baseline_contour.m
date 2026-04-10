function plot_baseline_contour(targetFolder)
% ==========================================================
% Plot baseline-subtracted amplitudes as 2D contour
% ==========================================================

data = load(fullfile(targetFolder,'baseline_subtracted.mat'));
sub = data.subtracted;

pos = sub.bin_values(:);
amps = sub.diffVals;     % [nBins x nPairs]
labels = sub.labels;
nPairs = numel(labels);

% Replace NaNs with 0 for plotting (optional)
ampsPlot = amps;
ampsPlot(isnan(ampsPlot)) = 0;

% Build grid for contourf
[X,Y] = meshgrid(1:nPairs, pos);

figure('Color','w','Position',[100,100,1400,600]);
contourf(X,Y,ampsPlot,30,'LineColor','none');
colormap jet; colorbar;
c = colorbar;
c.Label.String = 'Baseline-subtracted amplitude (\mu rad^2)';

xlabel('Pair index');
ylabel('Delay stage position (mm)');
title('Baseline-subtracted contour (pos vs pair index)');

% Optional: set X tick labels to actual pair labels
xticks(1:nPairs);
if nPairs <= 20
    xticklabels(labels);
    xtickangle(45);
end

end

function extra_analysis(cm, frame_dt_s, runFolder, CF_max, pairs, pairLabels)
% ==========================================================
% Extra analysis for Quantum Squeezing project
% - Running mean (64 channels, semilog)
% - Log–log evaluation of pairs
% - Heatmaps (mean, MSE, diagonal offset matrix)
% - Outputs in both V^2 and µrad^2
% ==========================================================
set(0, 'DefaultFigureVisible', 'off');
scale_to_urad2 = @(v) (v ./ CF_max) * 1e12; % V^2 → µrad^2

[N,~] = size(cm);

%% ---------- Running mean (64 channels) ----------
acu_sums_64 = zeros(N,64);
for ch = 1:64
    acu_sums_64(:,ch) = cumsum(cm(:,ch)) ./ (1:N)';
end
xvals = (1:N)' * frame_dt_s;

% Group into 8 subplots (one per row of the 8×8 matrix)
f_group = figure('Visible','off','Position',[100,100,1600,900]);
tiledlayout(2,4,'TileSpacing','compact'); % 8 subplots in 2x4

for row = 1:8
    nexttile;
    hold on;
    for col = 1:8
        idx = (row-1)*8 + col;
        yvals = abs(acu_sums_64(:,idx));
        yvals(yvals <= 0) = NaN;
        semilogy(xvals, yvals, 'DisplayName', sprintf('(%d,%d)',row,col));
    end
    xlabel('Time (s)');
    ylabel('Abs Running Mean (V^2)');
    title(sprintf('Row %d', row));
    grid on;
end
saveas(f_group, fullfile(runFolder,'semilogy_grouped_64channels_V2.png'));
close(f_group);

% µrad² grouped version
f_group = figure('Visible','off','Position',[100,100,1600,900]);
tiledlayout(2,4,'TileSpacing','compact');
for row = 1:8
    nexttile;
    hold on;
    for col = 1:8
        idx = (row-1)*8 + col;
        yvals = scale_to_urad2(abs(acu_sums_64(:,idx)));
        yvals(yvals <= 0) = NaN;
        semilogy(xvals, yvals, 'DisplayName', sprintf('(%d,%d)',row,col));
    end
    xlabel('Time (s)');
    ylabel('Abs Running Mean (\mu rad^2)');
    title(sprintf('Row %d', row));
    grid on;
end
saveas(f_group, fullfile(runFolder,'semilogy_grouped_64channels_urad2.png'));
close(f_group);


%% ---------- Log–log evaluation: ALL pairs, pure running-mean of cumsum ----------
% Requirements in workspace: cm, frame_dt_s, runFolder, CF_max, pairs, pairLabels

use_abs  = true;   % true: plot |running mean| on log-log; false: signed running mean (semilogx)
warmup_s = 1;

start_idx = max(1, round(warmup_s / frame_dt_s));
time_tail = ((start_idx:size(cm,1))' - 1) * frame_dt_s;
time_tail = time_tail - time_tail(1);
n_tail    = numel(time_tail);

scale_to_urad2 = @(v) (v ./ CF_max) * 1e12; % V^2 → µrad^2
idx_ch = @(r,c) sub2ind([8 8], r, c);

% (Optional) dedupe sign-equivalent reversals so we don't double-plot
canonKey = @(r1,c1,r2,c2) sprintf('%02d_%02d__%02d_%02d', ...
    min(r1,r2), min(c1,c2), max(r1,r2), max(c1,c2));
seen = containers.Map('KeyType','char','ValueType','logical');
keep = false(size(pairs,1),1);
for p = 1:size(pairs,1)
    r1=pairs(p,1); c1=pairs(p,2); r2=pairs(p,3); c2=pairs(p,4);
    k = canonKey(r1,c1,r2,c2);
    if ~isKey(seen,k)
        seen(k) = true;
        keep(p) = true;
    end
end
pairs_uni  = pairs(keep,:);
labels_uni = pairLabels(keep);
Puni       = size(pairs_uni,1);

% Precompute curves
curves = cell(Puni,1);
for p = 1:Puni
    r1 = pairs_uni(p,1); c1 = pairs_uni(p,2);
    r2 = pairs_uni(p,3); c2 = pairs_uni(p,4);
    i1 = idx_ch(r1,c1);  i2 = idx_ch(r2,c2);

    diffV2   = cm(start_idx:end, i1) - cm(start_idx:end, i2);   % V^2
    runMean  = cumsum(diffV2) ./ (1:n_tail)';                   % V^2
    runMeanU = scale_to_urad2(runMean);                         % µrad^2

    if use_abs
        y = abs(runMeanU);
        y(~isfinite(y) | y<=0) = NaN;  % for log-y
    else
        y = runMeanU;                  % signed; can be negative
        y(~isfinite(y)) = NaN;
    end
    curves{p} = y;
end

% Plot in groups of ≤8
max_lines_per_plot = 8;
group_starts = 1:max_lines_per_plot:Puni;
for g = 1:numel(group_starts)
    lo = group_starts(g);
    hi = min(lo + max_lines_per_plot - 1, Puni);
    idxList = lo:hi;

    f = figure('Visible','off','Position',[100 100 1000 700]); hold on;
    for ii = idxList
        plot(time_tail, curves{ii}, 'LineWidth', 1.8, 'DisplayName', labels_uni{ii});
    end
    if use_abs
        set(gca,'XScale','log','YScale','log');
        ylabel('Abs Running Mean (\mu rad^2)');
    else
        set(gca,'XScale','log');       % semilog-x, linear y for signed data
        ylabel('Running Mean (\mu rad^2)');
    end
    grid on; box on;
    xlabel('Time (s)');
    title(sprintf('Running-Mean of Cumsum (\\mu rad^2), Pairs %d–%d', idxList(1), idxList(end)), ...
          'Interpreter','none');
    legend('show','Location','bestoutside','Interpreter','none');

    outname = sprintf('loglog_eval_pairs_runmean_urad2_group_%02d.png', g);
    exportgraphics(f, fullfile(runFolder, outname), 'Resolution', 300);
    close(f);
end


%% ---------- Heatmaps ----------
matrix_mean = mean(cm);
matrix_mse  = mean((cm - matrix_mean).^2);
matrix_mean_8x8 = reshape(matrix_mean,8,8);
matrix_mse_8x8  = reshape(matrix_mse,8,8);

% V^2 heatmaps
f1 = figure('Visible','off','Position',[100,100,1200,500]);
tiledlayout(1,2,'TileSpacing','Compact');
nexttile;
h1 = heatmap(matrix_mean_8x8,'ColorbarVisible','on'); 
h1.CellLabelFormat = '%.2e'; title('Mean Corr (V^2)'); colormap(jet);
nexttile;
h2 = heatmap(matrix_mse_8x8,'ColorbarVisible','on'); 
h2.CellLabelFormat = '%.2e'; title('MSE Corr (V^4)'); colormap(jet);
saveas(f1, fullfile(runFolder,'combined_heatmap_V2.png')); 
close(f1);

% µrad^2 heatmap
matrix_mean_urad2 = scale_to_urad2(matrix_mean);
matrix_mean_urad2_8x8 = reshape(matrix_mean_urad2,8,8);
f2 = figure('Visible','off','Position',[100,100,600,500]);
h3 = heatmap(matrix_mean_urad2_8x8,'ColorbarVisible','on'); 
h3.CellLabelFormat = '%.2e'; title('Mean Corr (\mu rad^2)'); colormap(jet);
saveas(f2, fullfile(runFolder,'heatmap_mean_urad2.png')); 
close(f2);

%% ---------- Diagonal offset matrix ----------
diag_offset = zeros(8,8);
for d=-7:7
    diag_vals = diag(matrix_mean_8x8,d);
    if isempty(diag_vals), continue; end
    offset = diag_vals(end);
    for k=1:length(diag_vals)
        if d >= 0, i=k; j=k+d; else i=k-d; j=k; end
        diag_offset(i,j) = matrix_mean_8x8(i,j) - offset;
    end
end
f_diag = figure('Visible','off','Position',[100,100,600,500]);
h_diag = heatmap(diag_offset,'ColorbarVisible','on'); 
h_diag.CellLabelFormat = '%.2e'; 
title('Diagonal Tail-Offset (V^2)'); colormap(jet);
saveas(f_diag, fullfile(runFolder,'diagonal_offset_matrix_V2.png')); 
close(f_diag);

% µrad^2 version
diag_offset_urad2 = scale_to_urad2(diag_offset);
f_diag2 = figure('Visible','off','Position',[100,100,600,500]);
h_diag2 = heatmap(diag_offset_urad2,'ColorbarVisible','on'); 
h_diag2.CellLabelFormat = '%.2e'; 
title('Diagonal Tail-Offset (\mu rad^2)'); colormap(jet);
saveas(f_diag2, fullfile(runFolder,'diagonal_offset_matrix_urad2.png')); 
close(f_diag2);

end

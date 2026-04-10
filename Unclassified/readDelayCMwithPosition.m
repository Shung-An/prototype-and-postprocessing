%% Group CM frames by (binned) Position and aggregate
folderOut = uigetdir('Z:\Quantum Squeezing Project\DataFiles','Select Result Folder');
if folderOut == 0, return; end
inCSV = fullfile(folderOut,'cm_with_position.csv');
T = readtable(inCSV);

% Detect channel columns (assumes columns named C01..C64)
chVars = startsWith(T.Properties.VariableNames,'C');
if ~any(chVars)
    % fallback: assume columns 2..65 are channels (Timestamp, C01..C64, Position)
    chVars = false(1,width(T));
    chVars(2:min(65,width(T))) = true;
end

% ---- choose your binning method ----
pos_step = 0.01;               % <-- bin size in mm (e.g., 0.01 mm). Tweak as needed.
T.PosBin = round(T.Position/pos_step)*pos_step;

% (Alternative: tolerance-based binning around unique positions)
% pos_tol = 0.005;  % ±0.005 mm considered same
% [u,~,ic] = uniquetol(T.Position, pos_tol, 'ByRows', false);
% T.PosBin = u(ic);

% ---- aggregate by PosBin ----
Gmean = groupsummary(T,'PosBin','mean',T.Properties.VariableNames(chVars));
Gstd  = groupsummary(T,'PosBin','std', T.Properties.VariableNames(chVars));
Gcnt  = groupsummary(T,'PosBin','numel','Position');

% Clean column names a bit
Gmean.Properties.VariableNames = strrep(Gmean.Properties.VariableNames,'mean_','');
Gstd.Properties.VariableNames  = strrep(Gstd.Properties.VariableNames, 'std_','');
Gcnt.Properties.VariableNames{end} = 'Count';

% Save results
writetable(Gmean, fullfile(folderOut,'cm_grouped_by_position_mean.csv'));
writetable(Gstd,  fullfile(folderOut,'cm_grouped_by_position_std.csv'));
writetable(Gcnt,  fullfile(folderOut,'cm_grouped_by_position_counts.csv'));

disp('Wrote: cm_grouped_by_position_mean.csv, _std.csv, _counts.csv');

% Optional: quick sanity check – list bins with few samples
few = Gcnt.Count < 5;
if any(few)
    disp('Bins with <5 samples:');
    disp(Gcnt(few, {'PosBin','Count'}));
end

%% BPDLensPositionSilicon
% Estimate where to place a detector so the beam is intentionally defocused
% to a chosen spot size after a 50 mm lens.
%
% Assumptions:
% 1. The quoted 2 mm beam diameter is the 1/e^2 Gaussian diameter.
% 2. The input beam is approximately collimated at the lens.
% 3. The wavelength is 780 nm for the silicon-detector setup.

clear; clc; close all;

%% User inputs
lambda_nm = 780;                    % Laser wavelength [nm]
beam_diameter_mm = 2.0;            % 1/e^2 beam diameter at lens [mm]
focal_length_mm = 50.0;            % Lens focal length [mm]
detector_diameter_mm = 0.8;        % Desired 1/e^2 beam diameter at detector [mm]

%% Gaussian beam calculation
lambda_mm = lambda_nm * 1e-6;
w_in_mm = beam_diameter_mm / 2;
w_target_mm = detector_diameter_mm / 2;

% Focused waist for a collimated Gaussian beam passing through a thin lens.
w0_mm = lambda_mm * focal_length_mm / (pi * w_in_mm);
zR_mm = pi * w0_mm^2 / lambda_mm;

if w_target_mm < w0_mm
    error('Target detector radius is smaller than the diffraction-limited waist.');
end

dz_from_focus_mm = zR_mm * sqrt((w_target_mm / w0_mm)^2 - 1);
lens_to_detector_after_focus_mm = focal_length_mm + dz_from_focus_mm;
lens_to_detector_before_focus_mm = focal_length_mm - dz_from_focus_mm;

%% Sweep for plotting
z_plot_mm = linspace(max(0, focal_length_mm - 30), focal_length_mm + 30, 800);
w_plot_mm = w0_mm * sqrt(1 + ((z_plot_mm - focal_length_mm) / zR_mm).^2);
d_plot_mm = 2 * w_plot_mm;

%% Report
fprintf('Laser wavelength assumption: %.0f nm\n', lambda_nm);
fprintf('Input beam diameter at lens: %.3f mm\n', beam_diameter_mm);
fprintf('Lens focal length: %.3f mm\n', focal_length_mm);
fprintf('Detector target diameter: %.3f mm\n\n', detector_diameter_mm);

fprintf('Diffraction-limited waist diameter at focus: %.4f mm (%.1f um)\n', ...
    2 * w0_mm, 2 * w0_mm * 1e3);
fprintf('Rayleigh range around focus: %.4f mm\n', zR_mm);
fprintf('Required defocus from focus: %.4f mm\n', dz_from_focus_mm);
fprintf('Lens-to-detector distance after focus: %.4f mm\n', lens_to_detector_after_focus_mm);
fprintf('Lens-to-detector distance before focus: %.4f mm\n', lens_to_detector_before_focus_mm);

%% Plot and save PNG in the same folder
fig = figure('Color', 'w', 'Name', 'Defocused Spot Size at Detector');
plot(z_plot_mm, d_plot_mm, 'LineWidth', 2, 'Color', [0.1 0.35 0.75]); hold on;
yline(detector_diameter_mm, '--', 'Color', [0.85 0.2 0.2], 'LineWidth', 1.5);
xline(lens_to_detector_after_focus_mm, '--', 'Color', [0.15 0.6 0.25], 'LineWidth', 1.5);
scatter(lens_to_detector_after_focus_mm, detector_diameter_mm, 70, ...
    'MarkerFaceColor', [0.15 0.6 0.25], 'MarkerEdgeColor', 'k');
grid on;
xlabel('Lens-to-detector distance (mm)');
ylabel('1/e^2 spot diameter (mm)');
title('Defocused Gaussian Spot Size Near Focus');
legend('Spot diameter', 'Detector diameter target', 'Suggested detector position', ...
    'Location', 'northwest');

txt = sprintf(['Assumed \\lambda = %.0f nm\\n' ...
               'Focused waist diameter = %.1f \\mum\\n' ...
               'Suggested distance = %.2f mm'], ...
               lambda_nm, 2 * w0_mm * 1e3, lens_to_detector_after_focus_mm);
text(lens_to_detector_after_focus_mm + 1.2, detector_diameter_mm + 0.05, txt, ...
    'FontSize', 10, 'BackgroundColor', 'w', 'EdgeColor', [0.8 0.8 0.8]);

script_dir = fileparts(mfilename('fullpath'));
exportgraphics(fig, fullfile(script_dir, 'BPDLensPositionSilicon.png'), 'Resolution', 200);

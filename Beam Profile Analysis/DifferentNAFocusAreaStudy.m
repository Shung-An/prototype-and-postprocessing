%% DifferentNAFocusAreaStudy
% Study how numerical aperture (NA) affects diffraction-limited focus spot size.
% The model assumes a circular pupil and scalar diffraction formulas.
% This version is parameterized for an objective with NA_max = 0.28 and
% beam-diameter sweep starting from the current 2 mm beam.

clear; clc; close all;

%% User inputs
lambda_nm = 1064;                    % Wavelength in nm
lambda = lambda_nm * 1e-9;           % Wavelength in meters
n_medium = 1.0;                      % Refractive index of focusing medium (air = 1)

% Objective and beam settings
NA_max_objective = 0.28;             % Objective NA upper bound
beam_diam_current_mm = 2.0;          % Current beam diameter (lower bound of sweep)
beam_diam_full_fill_mm = 6.0;        % Beam diameter that fully fills objective pupil
n_points = 200;                      % Number of sweep points

% Sweep beam diameter from current beam (2 mm) to full-pupil fill.
beam_diam_mm = linspace(beam_diam_current_mm, beam_diam_full_fill_mm, n_points);

% Under-filled pupil scales effective NA linearly with fill ratio.
fill_ratio = beam_diam_mm / beam_diam_full_fill_mm;
fill_ratio = min(fill_ratio, 1);
NA = NA_max_objective * fill_ratio;

NA_lower = NA(1);
NA_upper = NA(end);

%% Diffraction-limited spot metrics
% Airy first-minimum radius (lateral): r_Airy = 0.61 * lambda / NA
r_airy = 0.61 * lambda ./ NA;                 % meters
d_airy = 2 * r_airy;                          % meters

% Approx. lateral intensity FWHM diameter for Airy-like focus
% d_FWHM ~= 0.51 * lambda / NA
d_fwhm = 0.51 * lambda ./ NA;                 % meters
r_fwhm = d_fwhm / 2;                          % meters

% Effective focal spot areas
A_airy = pi * r_airy.^2;                      % m^2
A_fwhm = pi * r_fwhm.^2;                      % m^2

% Axial depth-of-focus approximation in medium
% DOF ~= 2 * n * lambda / NA^2
DOF = 2 * n_medium * lambda ./ (NA.^2);       % meters

%% Endpoint metrics (current beam and full fill)
NA_endpoints = [NA_lower, NA_upper];
beam_endpoints_mm = [beam_diam_current_mm, beam_diam_full_fill_mm];
r_airy_ep = 0.61 * lambda ./ NA_endpoints;
d_fwhm_ep = 0.51 * lambda ./ NA_endpoints;
A_airy_ep = pi * r_airy_ep.^2;
A_fwhm_ep = pi * (d_fwhm_ep / 2).^2;
DOF_ep = 2 * n_medium * lambda ./ (NA_endpoints.^2);

%% Plot 1: Spot diameter vs NA
figure('Color', 'w', 'Name', 'Spot Diameter vs NA');
plot(NA, d_airy * 1e6, 'LineWidth', 2); hold on;
plot(NA, d_fwhm * 1e6, '--', 'LineWidth', 2);
scatter(NA_endpoints, (2 * r_airy_ep) * 1e6, 55, 'filled');
scatter(NA_endpoints, d_fwhm_ep * 1e6, 55, 'filled', 'MarkerFaceAlpha', 0.75);
grid on;
xlabel('Numerical Aperture (NA)');
ylabel('Diameter (\mum)');
title(sprintf('Focus Spot Diameter vs NA (NA range: %.3f to %.3f)', NA_lower, NA_upper));
legend('Airy Diameter (2\times0.61\lambda/NA)', ...
	'FWHM Diameter (0.51\lambda/NA)', ...
	'Endpoints Airy', ...
	'Endpoints FWHM', ...
	'Location', 'northeast');

%% Plot 2: Spot area vs NA (log scale)
figure('Color', 'w', 'Name', 'Spot Area vs NA');
semilogy(NA, A_airy * 1e12, 'LineWidth', 2); hold on;
semilogy(NA, A_fwhm * 1e12, '--', 'LineWidth', 2);
scatter(NA_endpoints, A_airy_ep * 1e12, 55, 'filled');
scatter(NA_endpoints, A_fwhm_ep * 1e12, 55, 'filled', 'MarkerFaceAlpha', 0.75);
grid on;
xlabel('Numerical Aperture (NA)');
ylabel('Area (\mum^2)');
title('Focus Spot Area vs NA');
legend('Airy Disk Area', 'FWHM Area', 'Endpoints Airy', 'Endpoints FWHM', 'Location', 'northeast');

%% Plot 3: DOF vs NA
figure('Color', 'w', 'Name', 'Depth of Focus vs NA');
plot(NA, DOF * 1e6, 'LineWidth', 2); hold on;
scatter(NA_endpoints, DOF_ep * 1e6, 55, 'filled');
grid on;
xlabel('Numerical Aperture (NA)');
ylabel('DOF (\mum)');
title('Depth of Focus vs NA');
legend('Model DOF', 'Endpoints DOF', 'Location', 'northeast');

%% Plot 4: Effective NA vs beam diameter
figure('Color', 'w', 'Name', 'Effective NA vs Beam Diameter');
plot(beam_diam_mm, NA, 'LineWidth', 2); hold on;
scatter(beam_endpoints_mm, NA_endpoints, 60, 'filled');
grid on;
xlabel('Beam Diameter at Objective (mm)');
ylabel('Effective NA');
title('Effective NA from Beam Fill');
legend('NA_{eff} = NA_{max} \times (D_{beam}/D_{full})', 'Endpoints', 'Location', 'southeast');

%% Summary table (lower and upper bounds)
T = table(beam_endpoints_mm(:), ...
          NA_endpoints(:), ...
	      (2 * r_airy_ep(:)) * 1e6, ...
	      d_fwhm_ep(:) * 1e6, ...
	      A_airy_ep(:) * 1e12, ...
	      A_fwhm_ep(:) * 1e12, ...
	      DOF_ep(:) * 1e6, ...
    'VariableNames', {'BeamDiameter_mm', 'NA', 'AiryDiameter_um', 'FWHMDiameter_um', 'AiryArea_um2', 'FWHMArea_um2', 'DOF_um'});

fprintf('Objective NA upper bound: %.3f\n', NA_max_objective);
fprintf('Current beam diameter lower bound: %.2f mm\n', beam_diam_current_mm);
fprintf('Computed NA sweep range: %.3f to %.3f\n\n', NA_lower, NA_upper);
disp('--- NA Focus Spot Study Summary (Bounds) ---');
disp(T);


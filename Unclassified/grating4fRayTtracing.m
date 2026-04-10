clear; clc; close all;

%% Parameters
lambda0 = 780e-9;
lambda_list = linspace(770e-9,790e-9,9);

g_mm = 1200;
g = g_mm*1e3;          % grooves/m
d = 1/g;
m1 = 1;
m2 = -1;
m3 = 1;
m4 = -1;

f = 200e-3;            % 200 mm
inputFreeSpaceLength = 150e-3; % free-space propagation before G1
freeSpaceLength = 150e-3;   % free-space propagation after G2
outputFreeSpaceLength = 150e-3; % free-space propagation after G4
debugTrace = true;          % print stage-by-stage progress checks

% Gaussian input beam setup
beamRadius = 1.5e-3;       % 1/e^2 Gaussian beam radius
numBeamRays = 9;           % number of rays used to represent the beam
x0_list = linspace(-beamRadius, beamRadius, numBeamRays);

% Pulse setup
tau0_fwhm = 100e-15;       % input pulse duration (FWHM)
c0 = 299792458;            % speed of light in vacuum (m/s)

% Grating angles to tune directly in degrees
phi1_deg = -27.9;
phi2_deg =  27.9;
phi3_deg =  -27.9;
phi4_deg =  27.9;
theta_in_deg = 0;      % incident angle before G1

% Positions
zIn   = 0;
zG1   = zIn + inputFreeSpaceLength;
zL1   = zG1 + f;
zMask = zG1 + 2*f;
zL2   = zG1 + 3*f;
zG2   = zG1 + 4*f;
zG3   = zG2 + freeSpaceLength;
zL3   = zG3 + f;
zMask2 = zG3 + 2*f;
zL4   = zG3 + 3*f;
zG4   = zG3 + 4*f;
zOut  = zG4 + outputFreeSpaceLength;

% Littrow angle at center wavelength
thetaL = asin(lambda0/(2*d));

% Reflective-grating geometry
phi1 = deg2rad(phi1_deg);   % grating-1 normal angle in lab frame
phi2 = deg2rad(phi2_deg);   % grating-2 normal angle in lab frame
phi3 = deg2rad(phi3_deg);   % grating-3 normal angle in lab frame
phi4 = deg2rad(phi4_deg);   % grating-4 normal angle in lab frame

% Input chief ray angle in the lab frame
theta_in = deg2rad(theta_in_deg);

% Thin lens matrix
LENS = @(ff) [1 0; -1/ff 1];

% Propagation helper
propagate = @(ray,L) [ray(1)+L*tan(ray(2)); ray(2)];

figure('Color','w'); hold on; box on;

xMask_center = nan(size(lambda_list));
xMask2_center = nan(size(lambda_list));
xOut_center = nan(size(lambda_list));
thetaMask_center = nan(size(lambda_list));
thetaMask2_center = nan(size(lambda_list));
thetaOut_center = nan(size(lambda_list));

if debugTrace
    fprintf('================ TRACE PROGRESS ===================\n');
    fprintf('theta_in = %+8.4f deg\n', rad2deg(theta_in));
    fprintf('thetaL   = %+8.4f deg\n', rad2deg(thetaL));
    fprintf('phi1/phi2/phi3/phi4 = [%+8.4f %+8.4f %+8.4f %+8.4f] deg\n', ...
        phi1_deg, phi2_deg, phi3_deg, phi4_deg);
    fprintf('m1/m2/m3/m4 = [%+d %+d %+d %+d]\n', m1, m2, m3, m4);
    fprintf('input free space = %.1f mm\n', inputFreeSpaceLength * 1e3);
    fprintf('middle free space = %.1f mm\n', freeSpaceLength * 1e3);
    fprintf('output free space = %.1f mm\n', outputFreeSpaceLength * 1e3);
    fprintf('===================================================\n');
end

numTraced = 0;

for k = 1:numel(lambda_list)
    lambda = lambda_list(k);
    for j = 1:numel(x0_list)
        % Start at the input plane with a Gaussian beam bundle
        ray = [x0_list(j); theta_in];
        zPts = zIn;
        xPts = ray(1);

        isCenterRay = j == ceil(numel(x0_list)/2);
        doDebug = debugTrace && isCenterRay;

        if doDebug
            fprintf('\nlambda = %6.1f nm\n', lambda * 1e9);
            fprintf('  start: x = %+8.4f mm, theta = %+8.4f deg\n', ...
                ray(1) * 1e3, rad2deg(ray(2)));
        end

        % Input free-space propagation
        ray = propagate(ray, zG1-zIn);
        zPts(end+1) = zG1;
        xPts(end+1) = ray(1);
        if doDebug
            fprintf('  at G1: x = %+8.4f mm, theta = %+8.4f deg\n', ...
                ray(1) * 1e3, rad2deg(ray(2)));
        end

        % G1 reflective grating
        [a, b] = reflective_grating_branches(ray(2), phi1, lambda, d, m1);
        ray(2) = pick_closest_branch(a, b, 0);
        if doDebug
            fprintf('  G1 branches: [%+8.4f %+8.4f] deg -> chosen %+8.4f deg\n', ...
                rad2deg(a), rad2deg(b), rad2deg(ray(2)));
        end
        if isnan(ray(2))
            if doDebug, fprintf('  STOP: invalid branch at G1\n'); end
            continue;
        end

        % G1 -> L1
        ray = propagate(ray, zL1-zG1);
        zPts(end+1) = zL1;
        xPts(end+1) = ray(1);
        if doDebug
            fprintf('  at L1: x = %+8.4f mm, theta = %+8.4f deg\n', ...
                ray(1) * 1e3, rad2deg(ray(2)));
        end

        % L1
        ray = LENS(f)*ray;

        % L1 -> Mask
        ray = propagate(ray, zMask-zL1);
        zPts(end+1) = zMask;
        xPts(end+1) = ray(1);
        if isCenterRay
            xMask_center(k) = ray(1);
            thetaMask_center(k) = ray(2);
        end
        if doDebug
            fprintf('  at Mask: x = %+8.4f mm, theta = %+8.4f deg\n', ...
                ray(1) * 1e3, rad2deg(ray(2)));
        end

        % L2 side: continue through mask plane
        ray = propagate(ray, zL2-zMask);
        zPts(end+1) = zL2;
        xPts(end+1) = ray(1);

        % L2
        ray = LENS(f)*ray;

        % L2 -> G2
        ray = propagate(ray, zG2-zL2);
        zPts(end+1) = zG2;
        xPts(end+1) = ray(1);
        if doDebug
            fprintf('  at G2: x = %+8.4f mm, theta = %+8.4f deg\n', ...
                ray(1) * 1e3, rad2deg(ray(2)));
        end

        % G2 reflective grating
        [a, b] = reflective_grating_branches(ray(2), phi2, lambda, d, m2);
        ray(2) = pick_closest_branch(a, b, 0);
        if doDebug
            fprintf('  G2 branches: [%+8.4f %+8.4f] deg -> chosen %+8.4f deg\n', ...
                rad2deg(a), rad2deg(b), rad2deg(ray(2)));
        end
        if isnan(ray(2))
            if doDebug, fprintf('  STOP: invalid branch at G2\n'); end
            continue;
        end

        % Free-space propagation
        ray = propagate(ray, zG3-zG2);
        zPts(end+1) = zG3;
        xPts(end+1) = ray(1);
        if doDebug
            fprintf('  at G3: x = %+8.4f mm, theta = %+8.4f deg\n', ...
                ray(1) * 1e3, rad2deg(ray(2)));
        end

        % G3 reflective grating
        [a, b] = reflective_grating_branches(ray(2), phi3, lambda, d, m3);
        ray(2) = pick_closest_branch(a, b, 0);
        if doDebug
            fprintf('  G3 branches: [%+8.4f %+8.4f] deg -> chosen %+8.4f deg\n', ...
                rad2deg(a), rad2deg(b), rad2deg(ray(2)));
        end
        if isnan(ray(2))
            if doDebug, fprintf('  STOP: invalid branch at G3\n'); end
            continue;
        end

        % G3 -> L3
        ray = propagate(ray, zL3-zG3);
        zPts(end+1) = zL3;
        xPts(end+1) = ray(1);
        if doDebug
            fprintf('  at L3: x = %+8.4f mm, theta = %+8.4f deg\n', ...
                ray(1) * 1e3, rad2deg(ray(2)));
        end

        % L3
        ray = LENS(f)*ray;

        % L3 -> Fourier plane 2
        ray = propagate(ray, zMask2-zL3);
        zPts(end+1) = zMask2;
        xPts(end+1) = ray(1);
        if isCenterRay
            xMask2_center(k) = ray(1);
            thetaMask2_center(k) = ray(2);
        end
        if doDebug
            fprintf('  at Mask2: x = %+8.4f mm, theta = %+8.4f deg\n', ...
                ray(1) * 1e3, rad2deg(ray(2)));
        end

        % Fourier plane 2 -> L4
        ray = propagate(ray, zL4-zMask2);
        zPts(end+1) = zL4;
        xPts(end+1) = ray(1);

        % L4
        ray = LENS(f)*ray;

        % L4 -> G4
        ray = propagate(ray, zG4-zL4);
        zPts(end+1) = zG4;
        xPts(end+1) = ray(1);
        if doDebug
            fprintf('  at G4: x = %+8.4f mm, theta = %+8.4f deg\n', ...
                ray(1) * 1e3, rad2deg(ray(2)));
        end

        % G4 reflective grating
        [a, b] = reflective_grating_branches(ray(2), phi4, lambda, d, m4);
        ray(2) = pick_closest_branch(a, b, 0);
        if doDebug
            fprintf('  G4 branches: [%+8.4f %+8.4f] deg -> chosen %+8.4f deg\n', ...
                rad2deg(a), rad2deg(b), rad2deg(ray(2)));
        end
        if isnan(ray(2))
            if doDebug, fprintf('  STOP: invalid branch at G4\n'); end
            continue;
        end

        % Output free-space propagation
        ray = propagate(ray, zOut-zG4);
        zPts(end+1) = zOut;
        xPts(end+1) = ray(1);
        if isCenterRay
            xOut_center(k) = ray(1);
            thetaOut_center(k) = ray(2);
        end
        if doDebug
            fprintf('  at Out: x = %+8.4f mm, theta = %+8.4f deg\n', ...
                ray(1) * 1e3, rad2deg(ray(2)));
            fprintf('  SUCCESS: path plotted with %d points\n', numel(zPts));
        end

        plot(zPts*1e3, xPts*1e3, 'LineWidth', 1.2);
        numTraced = numTraced + 1;
    end
end

fprintf('\nTraced %d of %d wavelength-ray combinations successfully.\n', ...
    numTraced, numel(lambda_list) * numel(x0_list));

fprintf('\nSpatial chirp diagnostic using center ray:\n');
for k = 1:numel(lambda_list)
    fprintf(['  lambda = %6.1f nm   x_Mask1 = %+8.4f mm   ' ...
             'x_Mask2 = %+8.4f mm   x_Out = %+8.4f mm\n'], ...
        lambda_list(k) * 1e9, xMask_center(k) * 1e3, ...
        xMask2_center(k) * 1e3, xOut_center(k) * 1e3);
end

chirpSpanMask1 = (max(xMask_center) - min(xMask_center)) * 1e3;
chirpSpanMask2 = (max(xMask2_center) - min(xMask2_center)) * 1e3;
chirpSpanOut = (max(xOut_center) - min(xOut_center)) * 1e3;

fprintf('\nSpatial chirp span:\n');
fprintf('  Mask1 span = %.4f mm\n', chirpSpanMask1);
fprintf('  Mask2 span = %.4f mm\n', chirpSpanMask2);
fprintf('  Out   span = %.4f mm\n', chirpSpanOut);

[tauMask1_fwhm, angChirpMask1, dtMask1] = estimate_pulse_duration_from_angular_chirp( ...
    lambda_list, thetaMask_center, tau0_fwhm, beamRadius, c0);
[tauMask2_fwhm, angChirpMask2, dtMask2] = estimate_pulse_duration_from_angular_chirp( ...
    lambda_list, thetaMask2_center, tau0_fwhm, beamRadius, c0);
[tauOut_fwhm, angChirpOut, dtOut] = estimate_pulse_duration_from_angular_chirp( ...
    lambda_list, thetaOut_center, tau0_fwhm, beamRadius, c0);

fprintf('\nPulse duration evolution (input pulse = %.1f fs FWHM):\n', tau0_fwhm * 1e15);
fprintf('  Input  : tau = %8.3f fs\n', tau0_fwhm * 1e15);
fprintf('  Mask1  : tau = %8.3f fs, dtheta/dlambda = %+8.4f mrad/nm, dt = %8.3f fs\n', ...
    tauMask1_fwhm * 1e15, angChirpMask1 * 1e12, dtMask1 * 1e15);
fprintf('  Mask2  : tau = %8.3f fs, dtheta/dlambda = %+8.4f mrad/nm, dt = %8.3f fs\n', ...
    tauMask2_fwhm * 1e15, angChirpMask2 * 1e12, dtMask2 * 1e15);
fprintf('  Output : tau = %8.3f fs, dtheta/dlambda = %+8.4f mrad/nm, dt = %8.3f fs\n', ...
    tauOut_fwhm * 1e15, angChirpOut * 1e12, dtOut * 1e15);

yl = ylim;
plot([zIn zIn]*1e3, yl, 'g--', 'LineWidth', 1.2);
plot([zG1 zG1]*1e3, yl, 'k--', 'LineWidth', 1.2);
plot([zL1 zL1]*1e3, yl, 'b-',  'LineWidth', 2);
plot([zMask zMask]*1e3, yl, 'm-', 'LineWidth', 2);
plot([zL2 zL2]*1e3, yl, 'b-',  'LineWidth', 2);
plot([zG2 zG2]*1e3, yl, 'k--', 'LineWidth', 1.2);
plot([zG3 zG3]*1e3, yl, 'k--', 'LineWidth', 1.2);
plot([zL3 zL3]*1e3, yl, 'b-',  'LineWidth', 2);
plot([zMask2 zMask2]*1e3, yl, 'm-', 'LineWidth', 2);
plot([zL4 zL4]*1e3, yl, 'b-',  'LineWidth', 2);
plot([zG4 zG4]*1e3, yl, 'k--', 'LineWidth', 1.2);
plot([zOut zOut]*1e3, yl, 'g--', 'LineWidth', 1.2);

text(zIn*1e3, yl(2)*0.9, 'In');
text(zG1*1e3, yl(2)*0.9, 'G1');
text(zL1*1e3, yl(2)*0.9, 'L1');
text(zMask*1e3, yl(2)*0.9, 'Mask');
text(zL2*1e3, yl(2)*0.9, 'L2');
text(zG2*1e3, yl(2)*0.9, 'G2');
text(zG3*1e3, yl(2)*0.9, 'G3');
text(zL3*1e3, yl(2)*0.9, 'L3');
text(zMask2*1e3, yl(2)*0.9, 'Mask2');
text(zL4*1e3, yl(2)*0.9, 'L4');
text(zG4*1e3, yl(2)*0.9, 'G4');
text(zOut*1e3, yl(2)*0.9, 'Out');

xlabel('z (mm)');
ylabel('x (mm)');
title('Reflective-grating pulse shaper with full 4-grating setup');
grid on;

figure('Color','w', 'Position', [140 140 900 700]);

subplot(3,1,1);
plot(lambda_list * 1e9, xMask_center * 1e3, 'o-', 'LineWidth', 1.8);
xlabel('\lambda (nm)');
ylabel('x at Mask1 (mm)');
title('Spatial chirp at Fourier plane 1');
grid on;

subplot(3,1,2);
plot(lambda_list * 1e9, xMask2_center * 1e3, 'o-', 'LineWidth', 1.8);
xlabel('\lambda (nm)');
ylabel('x at Mask2 (mm)');
title('Spatial chirp at Fourier plane 2');
grid on;

subplot(3,1,3);
plot(lambda_list * 1e9, xOut_center * 1e3, 'o-', 'LineWidth', 1.8);
xlabel('\lambda (nm)');
ylabel('x at Out (mm)');
title('Spatial chirp at output plane');
grid on;

figure('Color','w', 'Position', [220 220 700 450]);
planeIdx = 1:4;
tauEvolution_fs = 1e15 * [tau0_fwhm, tauMask1_fwhm, tauMask2_fwhm, tauOut_fwhm];
plot(planeIdx, tauEvolution_fs, 'o-', 'LineWidth', 1.8, 'MarkerSize', 7);
xlim([1 4]);
xticks(planeIdx);
xticklabels({'Input', 'Mask1', 'Mask2', 'Out'});
ylabel('Pulse duration (fs FWHM)');
title('Pulse duration evolution');
grid on;

% Spatial-chirp effect visualized as wavelength-dependent Gaussian spots
xProfile = linspace(-8e-3, 8e-3, 1201);
I_mask1_lambda = zeros(numel(lambda_list), numel(xProfile));
I_mask2_lambda = zeros(numel(lambda_list), numel(xProfile));
I_out_lambda = zeros(numel(lambda_list), numel(xProfile));

for k = 1:numel(lambda_list)
    I_mask1_lambda(k, :) = exp(-2 * ((xProfile - xMask_center(k)).^2) / beamRadius^2);
    I_mask2_lambda(k, :) = exp(-2 * ((xProfile - xMask2_center(k)).^2) / beamRadius^2);
    I_out_lambda(k, :) = exp(-2 * ((xProfile - xOut_center(k)).^2) / beamRadius^2);
end

I_mask1_sum = sum(I_mask1_lambda, 1);
I_mask2_sum = sum(I_mask2_lambda, 1);
I_out_sum = sum(I_out_lambda, 1);

I_mask1_sum = I_mask1_sum / max(I_mask1_sum);
I_mask2_sum = I_mask2_sum / max(I_mask2_sum);
I_out_sum = I_out_sum / max(I_out_sum);

figure('Color','w', 'Position', [180 180 1100 850]);

subplot(3,2,1);
imagesc(xProfile * 1e3, lambda_list * 1e9, I_mask1_lambda);
set(gca, 'YDir', 'normal');
xlabel('x (mm)');
ylabel('\lambda (nm)');
title('Spatial chirp effect at Mask1');
colorbar;

subplot(3,2,2);
plot(xProfile * 1e3, I_mask1_sum, 'LineWidth', 1.8);
xlabel('x (mm)');
ylabel('Normalized intensity');
title('Summed beam profile at Mask1');
grid on;

subplot(3,2,3);
imagesc(xProfile * 1e3, lambda_list * 1e9, I_mask2_lambda);
set(gca, 'YDir', 'normal');
xlabel('x (mm)');
ylabel('\lambda (nm)');
title('Spatial chirp effect at Mask2');
colorbar;

subplot(3,2,4);
plot(xProfile * 1e3, I_mask2_sum, 'LineWidth', 1.8);
xlabel('x (mm)');
ylabel('Normalized intensity');
title('Summed beam profile at Mask2');
grid on;

subplot(3,2,5);
imagesc(xProfile * 1e3, lambda_list * 1e9, I_out_lambda);
set(gca, 'YDir', 'normal');
xlabel('x (mm)');
ylabel('\lambda (nm)');
title('Spatial chirp effect at output');
colorbar;

subplot(3,2,6);
plot(xProfile * 1e3, I_out_sum, 'LineWidth', 1.8);
xlabel('x (mm)');
ylabel('Normalized intensity');
title('Summed beam profile at output');
grid on;

function [theta_out_1, theta_out_2] = reflective_grating_branches(theta_in, phi_g, lambda, d, m)
    alpha = theta_in - phi_g;
    s = m*lambda/d - sin(alpha);

    if abs(s) > 1
        theta_out_1 = NaN;
        theta_out_2 = NaN;
        return;
    end

    beta1 = asin(s);
    beta2 = pi - beta1;

    theta_out_1 = wrap_local(phi_g + beta1);
    theta_out_2 = wrap_local(phi_g + beta2);
end

function theta_out = pick_closest_branch(theta1, theta2, theta_target)
    if isnan(theta1) && isnan(theta2)
        theta_out = NaN;
        return;
    elseif isnan(theta1)
        theta_out = theta2;
        return;
    elseif isnan(theta2)
        theta_out = theta1;
        return;
    end

    d1 = abs(angle_diff(theta1, theta_target));
    d2 = abs(angle_diff(theta2, theta_target));

    if d1 <= d2
        theta_out = theta1;
    else
        theta_out = theta2;
    end
end

function dtheta = angle_diff(a, b)
    dtheta = atan2(sin(a-b), cos(a-b));
end

function a = wrap_local(a)
    a = atan2(sin(a), cos(a));
end

function [tau_fwhm, ang_chirp, dt_chirp] = estimate_pulse_duration_from_angular_chirp( ...
    lambda_list, theta_list, tau0_fwhm, beamRadius, c0)
    valid = isfinite(lambda_list) & isfinite(theta_list);
    if nnz(valid) < 3
        tau_fwhm = NaN;
        ang_chirp = NaN;
        dt_chirp = NaN;
        return;
    end

    lambda_valid = lambda_list(valid);
    theta_valid = theta_list(valid);

    p = polyfit(lambda_valid, theta_valid, 1);
    ang_chirp = p(1); % rad / m

    delta_lambda = max(lambda_valid) - min(lambda_valid);
    dt_chirp = abs(beamRadius * ang_chirp * delta_lambda / c0);
    tau_fwhm = sqrt(tau0_fwhm^2 + dt_chirp^2);
end

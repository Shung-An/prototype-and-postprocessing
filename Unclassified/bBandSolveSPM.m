wavelength = [600:10:1600]; % Wavelength range from 600 to 1600 nm
dispersion = [-323.3, -307.3, -292.5, -278.6, -265.7, -253.6, -242.3, -231.7, -221.8, -212.4, ...
              -203.7, -195.4, -187.7, -180.4, -173.5, -167.0, -160.8, -155.0, -149.4, -144.2, ...
              -139.2, -134.5, -130.0, -125.7, -121.6, -117.7, -113.9, -110.4, -106.9, -103.6, ...
              -100.5, -97.4, -94.5, -91.7, -89.0, -86.4, -83.8, -81.4, -79.0, -76.6, ...
              -74.4, -72.2, -70.1, -68.0, -66.0, -64.0, -62.1, -60.2, -58.3, -56.5, ...
              -54.7, -52.9, -51.2, -49.5, -47.8, -46.2, -44.5, -42.9, -41.3, -39.7, ...
              -38.2, -36.6, -35.1, -33.6, -32.1, -30.6, -29.1, -27.7, -26.2, -24.8, ...
              -23.4, -22.0, -20.6, -19.2, -17.8, -16.5, -15.1, -13.8, -12.4, -11.2, ...
              -9.8, -8.5, -7.3, -5.9, -4.7, -3.5, -2.2, -1.0, 0.3, 1.5, ...
              2.7, 3.9, 5.1, 6.3, 7.5, 8.6, 9.8, 10.9, 12.1, 13.2, 14.3];
% Interpolating to 1 nm resolution
new_wavelength = 600:1:1600; % New wavelength range with 1 nm resolution
interp_dispersion = interp1(wavelength, dispersion, new_wavelength, 'spline'); % Interpolate dispersion data
thicknessOfGlass = 150; %mm

% Constants
m = -1; % order of diffraction, Littrow configuration
M = 1; % magnification of 4f system
Goove = 1800; % lines/mm
Lambda = 1/Goove * 1e6; % grating spacing, nm
incident_angle = 36.52 / 180 * pi; % rad
dt_flint2 = 120; % fs, pulse duration from flint system

% Calculate sin(theta) for each wavelength
sin_theta = new_wavelength / (2 * Lambda);
cos_theta = sqrt(1 - sin_theta.^2); 
new_wavelength_meter = new_wavelength*1e-9;
% L_eff range from -0.03 to 0.03
L_eff_values = linspace(0.2, 1.2, 1000);
[GDD_Glass, TOD_Glass] = dispersionOfGlass(new_wavelength,0,thicknessOfGlass);
% Preallocate storage for pulse duration results
dt_GDD_grating_fiber = zeros(length(L_eff_values), length(new_wavelength));
GDD_grating_values = zeros(length(L_eff_values), length(new_wavelength)); % Store GDD grating

% Calculate GVD and GDD for fiber with interpolated dispersion
GVD_fiber = -new_wavelength.^2 / (2 * pi * 3e8) .* interp_dispersion * 1e6; % fs^2/m
GDD_fiber = GVD_fiber * 50; % fs^2
dt_GDD_only_fiber = sqrt(dt_flint2^2 + (4*log(2).*GDD_fiber/dt_flint2).^2)/1e3; % ps
% Compute the numerical derivative retaining the same size
TOD_fiber = ((new_wavelength_meter.^2/2/pi/3e8).^2    .*gradient(interp_dispersion, new_wavelength)*1e3+new_wavelength_meter.^3/2/pi^2/9e16.*interp_dispersion*1e-6)*50*1e45;% fs^3

% Compute dt_GDD_and_fiber for each L_eff
for i = 1:length(L_eff_values)
    L_eff = L_eff_values(i);
    GDD_grating = -2 * m^2 * new_wavelength.^3 * 1e-9  * L_eff / (2 * pi * 9e16 * Lambda^2) * 1e30; % fs^2
    GDD_grating_and_Fiber_Glass = GDD_grating + GDD_fiber + GDD_Glass; % fs^2
    TOD_grating(i,:) = -GDD_grating .*3.*new_wavelength.*1e-9./.2./pi./3e8.*1e15; %fs^3
    dt_GDD_grating_fiber_glass(i, :) = sqrt(dt_flint2^2 + (4 * log(2) .* GDD_grating_and_Fiber_Glass / dt_flint2).^2) / 1e3; % ps
    
    % Store GDD grating for plotting
    GDD_grating_values(i, :) = GDD_grating;
end
%%
% Plot all results in one figure
figure;
% Generate a colormap (gradient from blue to red) for 100 L_eff values
cmap = jet(length(L_eff_values)); 
% Subplot 1: Plot cos(theta) as a function of wavelength
subplot(3, 1, 1);
hold on;
for i = 1:length(L_eff_values) % Plot every 10th L_eff for clarity
    plot(new_wavelength, TOD_grating(i, :), 'Color', cmap(i, :));
end
plot (new_wavelength, TOD_fiber,'b--');
colormap(cmap); % Apply the colormap
cb1 = colorbar; % Show the colorbar to indicate L_eff values
caxis([min(L_eff_values*100) max(L_eff_values*100)]); % Set the colorbar axis limits to match L_eff range
xlabel('Wavelength (nm)');
ylabel('TOD (fs^3)');
xlim([600 900]);
ylabel(cb1, 'L_{eff} (cm)'); % Label the colorbar with L_eff
title('TOD of grating and fibe vs Wavelength');
grid on;


% Subplot 2: Pulse Duration vs Wavelength for Various L_{eff}
subplot(3, 1, 2);
hold on;
for i = 1:length(L_eff_values) % Plot every 10th L_eff for clarity
    plot(new_wavelength, dt_GDD_grating_fiber_glass(i, :), 'Color', cmap(i, :));
end
plot(new_wavelength, dt_GDD_only_fiber, 'k--', 'LineWidth', 2, 'DisplayName', 'GDD only fiber');
xlabel('Wavelength (nm)');
ylabel('Pulse Duration (ps)');
xlim([600 900]);
ylim([0 5]);
title('Pulse Duration vs Wavelength for 100 L_{eff} Values');
grid on;
colormap(cmap); % Apply the colormap
cb1 = colorbar; % Show the colorbar to indicate L_eff values
ylabel(cb1, 'L_{eff} (cm)'); % Label the colorbar with L_eff
caxis([min(L_eff_values*100) max(L_eff_values*100)]); % Set the colorbar axis limits to match L_eff range
hold off;

% Subplot 3: GDD_fiber and GDD_grating vs Wavelength
subplot(3, 1, 3);
hold on;
plot(new_wavelength, GDD_Glass, 'r--', 'LineWidth', 2, 'DisplayName', 'GDD Fiber');
for i = 1:length(L_eff_values) % Plot every 10th L_eff for clarity
    plot(new_wavelength, GDD_grating_values(i, :), 'Color', cmap(i, :));
end
xlabel('Wavelength (nm)');
ylabel('Group Delay Dispersion (fs^2)');
ylim([-1e7 1e7]);
xlim([600 900]);
title('GDD of grating and fiber vs Wavelength');
plot(new_wavelength, GDD_fiber,'k--');
colormap(cmap); % Apply the colormap
cb2 = colorbar; % Show the colorbar for L_eff values
ylabel(cb2, 'L_{eff} (cm)'); % Label the colorbar with L_eff
caxis([min(L_eff_values*100) max(L_eff_values*100)]); % Set the colorbar axis limits to match L_eff range
grid on;
hold off;
sgtitle('290R Plane Ruled Diffraction Grating 1800 lines/mm'); 
